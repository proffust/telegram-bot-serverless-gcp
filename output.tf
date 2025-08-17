# Вывод URL функции
output "function_url" {
  value = google_cloudfunctions2_function.telegram_bot_function.url
}
