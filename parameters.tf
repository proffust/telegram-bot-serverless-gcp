resource "google_parameter_manager_regional_parameter" "allowed_models_openai" {
  parameter_id = "allowed_models_openai"
  format = "JSON"
  location = var.region
}

resource "google_parameter_manager_regional_parameter_version" "allowed_models_openai_version" {
  parameter = google_parameter_manager_regional_parameter.allowed_models_openai.id
  parameter_version_id = "v1"
  parameter_data = jsonencode(var.allowed_models_openai)
}

resource "google_parameter_manager_regional_parameter" "allowed_models_antropic" {
  parameter_id = "allowed_models_antropic"
  format = "JSON"
  location = var.region
}

resource "google_parameter_manager_regional_parameter_version" "allowed_models_antropic_version" {
  parameter = google_parameter_manager_regional_parameter.allowed_models_antropic.id
  parameter_version_id = "v1"
  parameter_data = jsonencode(var.allowed_models_antropic)
}

resource "google_parameter_manager_regional_parameter" "allowed_models_xai" {
  parameter_id = "allowed_models_xai"
  format = "JSON"
  location = var.region
}

resource "google_parameter_manager_regional_parameter_version" "allowed_models_xai_version" {
  parameter = google_parameter_manager_regional_parameter.allowed_models_xai.id
  parameter_version_id = "v1"
  parameter_data = jsonencode(var.allowed_models_xai)
}

resource "google_parameter_manager_regional_parameter" "allowed_models_google" {
  parameter_id = "allowed_models_google"
  format = "JSON"
  location = var.region
}

resource "google_parameter_manager_regional_parameter_version" "allowed_models_google_version" {
  parameter = google_parameter_manager_regional_parameter.allowed_models_google.id
  parameter_version_id = "v1"
  parameter_data = jsonencode(var.allowed_models_google)
}

# resource "google_secret_manager_secret" "telegram_token" {
#   secret_id = "TELEGRAM_TOKEN"
#   replication {
#     auto {}
#   }
# }

# resource "google_secret_manager_secret_version" "telegram_token_version" {
#   secret = google_secret_manager_secret.telegram_token.id
#   secret_data = var.telegram_token
# }