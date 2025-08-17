terraform {
  required_providers {
    telegram = {
      source = "yi-jiayu/telegram"
      version = "0.3.1"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

provider "telegram" {
  bot_token = sensitive(var.telegram_token)
}