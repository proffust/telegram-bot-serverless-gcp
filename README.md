# Описание

Этот проект содержит Terraform-конфигурации для развёртывания инфраструктуры в Google Cloud Platform (GCP).

## Требования для запуска

- Аккаунт в Google Cloud Platform
- Установленный [Terraform](https://www.terraform.io/downloads.html) версии 1.0 или выше
- Установленный [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Инициализированный и настроенный проект GCP
- Созданы секреты в Secret Manager:
    - `OPENAI_API_KEY`
    - `ANTHROPIC_API_KEY`
    - `TELEGRAM_TOKEN`
    - (при необходимости) `xAI` — если используется
- Добавлен файл `module.auto.tfvars` с вашими значениями переменных (например, `project`, `region`, `conversation_bucket`, `telegram_token`)
- В переменных `allowed_models_*` указаны списки моделей от разных поставщиков, которые могут быть использованы. Если список пуст - соотвествующий клиент не будет инициализирован
## Быстрый старт

1. Склонируйте репозиторий:
    ```sh
    git clone <URL-репозитория>
    cd telegram-bot-serverless-gcp
    ```
2. Инициализируйте Terraform:
    ```sh
    terraform init
    ```
3. Примените конфигурацию:
    ```sh
    terraform apply
    ```