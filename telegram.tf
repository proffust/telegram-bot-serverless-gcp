resource "telegram_bot_webhook" "webhook" {
  url = google_cloudfunctions2_function.telegram_bot_function.url
  depends_on = [
    google_cloudfunctions2_function.telegram_bot_function,
  ]
}

resource "telegram_bot_commands" "ai-bot-commands" {
  commands = [
    {
      command = "start",
      description = "Поздороваться"
    },
    {
      command = "image",
      description = "Генерация изображения по текстовому промпту"
    },
    {
      command = "new_session",
      description = "Начать новый сеанс общения с ботом"
    },
    {
      command = "get_model",
      description = "Вывод текущей используемой модели"
    },
    {
      command = "set_model",
      description = "Установка модели для общения с ботом"
    },
    {
      command = "help",
      description = "Поздороваться и рассказать о себе"
    }
  ]
}
