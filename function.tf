# Cloud Function (2nd gen)
resource "google_cloudfunctions2_function" "telegram_bot_function" {
  name        = "gcp-chat-bot-serverless"
  location    = var.region
  description = "Telegram bot function for handling messages and send requests to AI models"

  build_config {
    runtime     = "python311"
    entry_point = "message_handler"
    source {
      storage_source {
        bucket = google_storage_bucket.function_bucket.name
        object = google_storage_bucket_object.archive.name
      }
    }
    docker_repository = "projects/${var.project}/locations/${google_artifact_registry_repository.repo.location}/repositories/${google_artifact_registry_repository.repo.repository_id}"
  }

  service_config {
    max_instance_count = 10
    min_instance_count = 0
    available_memory   = "384Mi"
    timeout_seconds    = 60
    service_account_email = google_service_account.function_sa.email
    secret_environment_variables {
      key        = "OPENAI_API_KEY"
      project_id = var.project
      secret     = "OPENAI_API_KEY"
      version    = "latest"
    }
    secret_environment_variables {
      key        = "ANTHROPIC_API_KEY"
      project_id = var.project
      secret     = "ANTHROPIC_API_KEY"
      version    = "latest"
    }
    secret_environment_variables {
      key        = "TELEGRAM_TOKEN"
      project_id = var.project
      secret     = "TELEGRAM_TOKEN"
      version    = "latest"
    }
    secret_environment_variables {
      key        = "XAI_API_KEY"
      project_id = var.project
      secret     = "XAI_API_KEY"
      version    = "latest"
    }
    environment_variables = {
      CONVERSATION_BUCKET = var.conversation_bucket
      GCP_PROJECT         = var.project
      GCP_REGION          = var.region
    }
  }
  depends_on = [
    google_artifact_registry_repository.repo,
    google_storage_bucket.function_bucket,
    google_storage_bucket_object.archive,
    google_service_account.function_sa,
    google_project_iam_member.secret_accessor,
    google_storage_bucket_iam_member.gcf_admin
  ]
}
