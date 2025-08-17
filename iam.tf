
# IAM для публичного доступа к функции
resource "google_cloud_run_service_iam_member" "invoker" {
  project  = var.project
  location = google_cloudfunctions2_function.telegram_bot_function.location
  service  = split("/", google_cloudfunctions2_function.telegram_bot_function.name)[length(split("/", google_cloudfunctions2_function.telegram_bot_function.name)) - 1]
  role     = "roles/run.invoker"
  member   = "allUsers"
  depends_on = [
    google_cloudfunctions2_function.telegram_bot_function
  ]
}

# IAM для Artifact Registry
resource "google_artifact_registry_repository_iam_member" "repository_iam" {
  project    = var.project
  location   = google_artifact_registry_repository.repo.location
  repository = google_artifact_registry_repository.repo.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.function_sa.email}"
  depends_on = [
    google_artifact_registry_repository.repo
  ]
}

# Создание сервисного аккаунта для функции
resource "google_service_account" "function_sa" {
  account_id   = "gcp-chat-bot-serverless-sa"
  display_name = "Service Account for Cloud Function"
}

# IAM для Secret Manager
resource "google_project_iam_member" "secret_accessor" {
  project = var.project
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
  depends_on = [
    google_service_account.function_sa
  ]
}

resource "google_project_iam_member" "parameter_viewer" {
  project = var.project
  role    = "roles/parametermanager.parameterViewer"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
  depends_on = [
    google_service_account.function_sa
  ]
}

resource "google_project_iam_member" "project_viewer" {
  project = var.project
  role    = "roles/viewer"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
  depends_on = [
    google_service_account.function_sa
  ]
}

resource "google_project_iam_member" "vertex_api" {
  project = var.project
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
  depends_on = [
    google_service_account.function_sa
  ]
}

resource "google_storage_bucket_iam_member" "gcf_admin" {
  bucket = var.conversation_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.function_sa.email}"
  depends_on = [
    google_service_account.function_sa
  ]
}
