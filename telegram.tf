resource "telegram_bot_webhook" "webhook" {
  url = google_cloudfunctions2_function.telegram_bot_function.url
  depends_on = [
    google_cloudfunctions2_function.telegram_bot_function,
  ]
}
