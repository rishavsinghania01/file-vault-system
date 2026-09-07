import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .models import File, StoredBlob


def make_file(name="report.txt", content=b"hello world", content_type="text/plain"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def test_embedding(file_obj, file_type, content_type=""):
    file_obj.seek(0)
    text = file_obj.read().decode("utf-8", errors="ignore")
    file_obj.seek(0)
    vector = [1.0, 0.0] if "invoice" in text.lower() else [0.0, 1.0]
    return text, vector


class AuthenticatedVaultTestCase(APITestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = get_user_model().objects.create_user(
            username="rishav",
            password="StrongPass123!",
        )
        self.client.force_authenticate(self.user)
        self.embedding_patcher = patch(
            "files.views.build_document_embedding",
            side_effect=test_embedding,
        )
        self.embedding_patcher.start()
        self.addCleanup(self.embedding_patcher.stop)


class AuthenticationTests(APITestCase):
    def test_user_can_register_and_receive_tokens(self):
        response = self.client.post(
            reverse("auth-register"),
            {"username": "new-user", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_file_list_requires_authentication(self):
        response = self.client.get(reverse("file-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FileUploadDedupTests(AuthenticatedVaultTestCase):
    list_url = reverse("file-list")

    def test_uploading_new_file_creates_one_blob_and_one_reference(self):
        response = self.client.post(self.list_url, {"file": make_file()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["duplicate"])
        self.assertEqual(File.objects.count(), 1)
        self.assertEqual(StoredBlob.objects.count(), 1)
        reference = File.objects.get()
        self.assertEqual(reference.owner, self.user)
        self.assertTrue(reference.blob.file)
        self.assertEqual(len(reference.blob.sha256), 64)

    def test_identical_content_creates_two_references_to_one_blob(self):
        first = self.client.post(self.list_url, {"file": make_file("a.txt")}, format="multipart")
        second = self.client.post(self.list_url, {"file": make_file("b.txt")}, format="multipart")

        self.assertFalse(first.data["duplicate"])
        self.assertTrue(second.data["duplicate"])
        self.assertEqual(File.objects.count(), 2)
        self.assertEqual(StoredBlob.objects.count(), 1)
        references = list(File.objects.order_by("uploaded_at"))
        self.assertEqual(references[0].blob_id, references[1].blob_id)

    def test_different_content_is_never_deduplicated(self):
        self.client.post(self.list_url, {"file": make_file("a.txt", b"content-a")}, format="multipart")
        response = self.client.post(
            self.list_url,
            {"file": make_file("b.txt", b"content-b")},
            format="multipart",
        )
        self.assertFalse(response.data["duplicate"])
        self.assertEqual(StoredBlob.objects.count(), 2)

    def test_stats_report_storage_saved_by_reused_blob(self):
        self.client.post(self.list_url, {"file": make_file("a.txt", b"x" * 100)}, format="multipart")
        self.client.post(self.list_url, {"file": make_file("b.txt", b"x" * 100)}, format="multipart")

        response = self.client.get(reverse("file-stats"))
        self.assertEqual(response.data["total_files"], 2)
        self.assertEqual(response.data["unique_files"], 1)
        self.assertEqual(response.data["storage_used_bytes"], 100)
        self.assertEqual(response.data["storage_saved_bytes"], 100)


class UserIsolationTests(AuthenticatedVaultTestCase):
    list_url = reverse("file-list")

    def test_users_share_blob_storage_without_seeing_each_others_references(self):
        self.client.post(
            self.list_url,
            {"file": make_file("first-name.txt", b"shared bytes")},
            format="multipart",
        )
        second_user = get_user_model().objects.create_user(
            username="second-user",
            password="StrongPass123!",
        )
        self.client.force_authenticate(second_user)
        response = self.client.post(
            self.list_url,
            {"file": make_file("private-name.txt", b"shared bytes")},
            format="multipart",
        )
        self.assertTrue(response.data["duplicate"])
        self.assertEqual(StoredBlob.objects.count(), 1)

        listing = self.client.get(self.list_url)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["original_filename"], "private-name.txt")


class SemanticSearchTests(AuthenticatedVaultTestCase):
    list_url = reverse("file-list")

    @patch("files.views.embed_text", return_value=[1.0, 0.0])
    def test_semantic_search_ranks_by_embedding_similarity(self, query_embedding):
        self.client.post(
            self.list_url,
            {"file": make_file("billing.txt", b"invoice payment terms")},
            format="multipart",
        )
        self.client.post(
            self.list_url,
            {"file": make_file("holiday.txt", b"beach travel plan")},
            format="multipart",
        )

        response = self.client.get(reverse("file-semantic-search"), {"q": "billing document"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["original_filename"], "billing.txt")
        self.assertEqual(response.data["results"][0]["semantic_score"], 1.0)
        query_embedding.assert_called_once_with("billing document")


class FileSearchFilterTests(AuthenticatedVaultTestCase):
    list_url = reverse("file-list")

    def setUp(self):
        super().setUp()
        self.client.post(self.list_url, {"file": make_file("invoice.pdf", b"invoice", "application/pdf")}, format="multipart")
        self.client.post(self.list_url, {"file": make_file("photo.png", b"b" * 1000, "image/png")}, format="multipart")
        self.client.post(self.list_url, {"file": make_file("notes.txt", b"c" * 50)}, format="multipart")

    def test_search_by_filename(self):
        response = self.client.get(self.list_url, {"search": "invoice"})
        self.assertEqual([item["original_filename"] for item in response.data["results"]], ["invoice.pdf"])

    def test_filter_by_size_range(self):
        response = self.client.get(self.list_url, {"min_size": 40, "max_size": 60})
        self.assertEqual([item["original_filename"] for item in response.data["results"]], ["notes.txt"])


class FileDeleteTests(AuthenticatedVaultTestCase):
    list_url = reverse("file-list")

    def test_deleting_one_reference_keeps_a_shared_blob(self):
        first = self.client.post(self.list_url, {"file": make_file("a.txt")}, format="multipart")
        second = self.client.post(self.list_url, {"file": make_file("b.txt")}, format="multipart")

        response = self.client.delete(reverse("file-detail", args=[first.data["data"]["id"]]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(File.objects.count(), 1)
        self.assertEqual(StoredBlob.objects.count(), 1)
        self.assertTrue(File.objects.get(pk=second.data["data"]["id"]).blob.file)

    def test_deleting_last_reference_removes_its_blob(self):
        upload = self.client.post(self.list_url, {"file": make_file("solo.txt")}, format="multipart")
        response = self.client.delete(reverse("file-detail", args=[upload.data["data"]["id"]]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(File.objects.count(), 0)
        self.assertEqual(StoredBlob.objects.count(), 0)
