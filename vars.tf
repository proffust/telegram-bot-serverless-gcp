variable project {
  type        = string
  default     = ""
  description = "Project name for the resources in GCP"
}

variable region {
  type        = string
  default     = ""
  description = "Region for the resources in GCP"
}

variable conversation_bucket {
  type        = string
  default     = ""
  description = "Bucket for storing conversations"
}

variable allowed_models_openai {
  type        = list(string)
  default     = []
  description = "List of allowed OpenAI models"
}

variable allowed_models_antropic {
  type        = list(string)
  default     = []
  description = "List of allowed Anthropic models"
}

variable allowed_models_xai {
  type        = list(string)
  default     = []
  description = "List of allowed XAI models"
}

variable allowed_models_google {
  type        = list(string)
  default     = []
  description = "List of allowed Google models"
}

variable telegram_token {
  type        = string
  default     = ""
  description = "Telegram bot token"
}