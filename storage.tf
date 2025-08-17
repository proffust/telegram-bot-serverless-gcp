# Создание репозитория в Artifact Registry
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "cloud-functions-repo"
  description   = "Repository for Cloud Functions"
  format        = "DOCKER"

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "delete-old-versions"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 дней
      tag_state  = "UNTAGGED"
    }
  }
}

# Bucket для кода
resource "google_storage_bucket" "function_bucket" {
  name     = "terraform-function-bucket-${var.project}"
  location = var.region
  uniform_bucket_level_access = true
  force_destroy = true
  
  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }
}

# Загрузка архива
resource "google_storage_bucket_object" "archive" {
  name   = "function-${data.archive_file.source.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.source.output_path
  depends_on = [
    data.archive_file.source
  ]
}

# bucket для хранения разговоров
resource "google_storage_bucket" "conversation_bucket" {
  name     = var.conversation_bucket
  location = var.region
  uniform_bucket_level_access = true
  force_destroy = false
}
