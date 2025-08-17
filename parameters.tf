resource "google_parameter_manager_regional_parameter" "allowed_models" {
  parameter_id = "allowed_models"
  format = "JSON"
  location = var.region
}

resource "google_parameter_manager_regional_parameter_version" "allowed_models_version" {
  parameter = google_parameter_manager_regional_parameter.allowed_models.id
  parameter_version_id = "v1"
  parameter_data = jsonencode({
      "openai": var.allowed_models_openai,
      "antropic": var.allowed_models_antropic,
      "xai": var.allowed_models_xai,
      "google": var.allowed_models_google
    }  
  )
}
