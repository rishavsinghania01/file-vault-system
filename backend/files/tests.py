"""Tests covering the two headline features: deduplication and search/filtering,
plus the delete-with-promotion and stats behaviour that support them."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import File


def make_file(name="report.txt", content=b"hello world", content_type="text/plain"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class FileUploadDedupTests(APITestCase):
    list_url = reverse("file-list")

    def test_uploading_new_file_creates_a_record_with_hash(self):
        response = self.client.post(self.list_url, {"file": make_file()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["duplicate"])
        self.assertEqual(File.objects.count(), 1)
        stored = File.objects.first()
        self.assertIsNotNone(stored.hash)
        self.assertTrue(stored.file)

    def test_uploading_identical_content_creates_a_duplicate_reference(self):
        first = self.client.post(self.list_url, {"file": make_file("a.txt")}, format="multipart")
        second = self.client.post(self.list_url, {"file": make_file("b.txt")}, format="multipart")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertFalse(first.data["duplicate"])
        self.assertTrue(second.data["duplicate"])

        self.assertEqual(File.objects.count(), 2)
        duplicate = File.objects.get(pk=second.data["data"]["id"])
        self.assertIsNotNone(duplicate.original_id)
        self.assertFalse(duplicate.file)  # no physical copy stored

    def test_different_content_is_never_deduplicated(self):
        self.client.post(self.list_url, {"file": make_file("a.txt", b"content-a")}, format="multipart")
        response = self.client.post(self.list_url, {"file": make_file("b.txt", b"content-b")}, format="multipart")
        self.assertFalse(response.data["duplicate"])
        self.assertEqual(File.objects.count(), 2)

    def test_stats_report_storage_saved_by_deduplication(self):
        self.client.post(self.list_url, {"file": make_file("a.txt", b"x" * 100)}, format="multipart")
        self.client.post(self.list_url, {"file": make_file("b.txt", b"x" * 100)}, format="multipart")

        response = self.client.get(reverse("file-stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_files"], 2)
        self.assertEqual(response.data["unique_files"], 1)
        self.assertEqual(response.data["duplicate_files"], 1)
        self.assertEqual(response.data["storage_saved_bytes"], 100)


class FileSearchFilterTests(APITestCase):
    list_url = reverse("file-list")

    def setUp(self):
        self.client.post(self.list_url, {"file": make_file("invoice.pdf", b"a" * 10, "application/pdf")}, format="multipart")
        self.client.post(self.list_url, {"file": make_file("photo.png", b"b" * 1000, "image/png")}, format="multipart")
        self.client.post(self.list_url, {"file": make_file("notes.txt", b"c" * 50, "text/plain")}, format="multipart")

    def test_search_by_filename(self):
        response = self.client.get(self.list_url, {"search": "invoice"})
        names = [f["original_filename"] for f in response.data["results"]]
        self.assertEqual(names, ["invoice.pdf"])

    def test_filter_by_file_type(self):
        response = self.client.get(self.list_url, {"file_type": "png"})
        names = [f["original_filename"] for f in response.data["results"]]
        self.assertEqual(names, ["photo.png"])

    def test_filter_by_size_range(self):
        response = self.client.get(self.list_url, {"min_size": 40, "max_size": 60})
        names = [f["original_filename"] for f in response.data["results"]]
        self.assertEqual(names, ["notes.txt"])

    def test_combined_filters(self):
        response = self.client.get(self.list_url, {"file_type": "png", "min_size": 500})
        names = [f["original_filename"] for f in response.data["results"]]
        self.assertEqual(names, ["photo.png"])

        response = self.client.get(self.list_url, {"file_type": "png", "min_size": 5000})
        self.assertEqual(response.data["results"], [])


class FileDeletePromotionTests(APITestCase):
    list_url = reverse("file-list")

    def test_deleting_an_original_promotes_a_duplicate(self):
        first = self.client.post(self.list_url, {"file": make_file("a.txt")}, format="multipart")
        second = self.client.post(self.list_url, {"file": make_file("b.txt")}, format="multipart")
        original_id = first.data["data"]["id"]
        duplicate_id = second.data["data"]["id"]

        delete_url = reverse("file-detail", args=[original_id])
        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        promoted = File.objects.get(pk=duplicate_id)
        self.assertIsNone(promoted.original_id)
        self.assertTrue(promoted.file)

    def test_deleting_only_copy_removes_the_row(self):
        first = self.client.post(self.list_url, {"file": make_file("solo.txt")}, format="multipart")
        file_id = first.data["data"]["id"]
        delete_url = reverse("file-detail", args=[file_id])
        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(File.objects.count(), 0)
