# Описание

Этот проект содержит Terraform-конфигурации для развёртывания инфраструктуры в Google Cloud Platform (GCP).

## Требования для запуска

- Аккаунт в Google Cloud Platform
- Установленный [Terraform](https://www.terraform.io/downloads.html) версии 1.0 или выше
- Установленный [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Инициализированный и настроенный проект GCP
- Созданный телеграм бот
- Созданы секреты в Secret Manager:
    - `OPENAI_API_KEY`
    - `ANTHROPIC_API_KEY`
    - `TELEGRAM_TOKEN`
    - `XAI_API_KEY`
- Добавлен файл `module.auto.tfvars` с вашими значениями переменных ( `project`, `region`, `telegram_token`)
- Добавлен файл `models_list.auto.tfvars` с переменными `allowed_models_*` указаны списки моделей от разных поставщиков, которые могут быть использованы. Если список пуст - соотвествующий клиент не будет инициализирован и `conversation_bucket`
- Создан бакет для terraform state `terraform-state-bucket-имя_вашего_проекта_в_GCP`
## Быстрый старт

1. Склонируйте репозиторий:
    ```sh
    git clone <URL-репозитория>
    cd telegram-bot-serverless-gcp
    ```
2. Инициализируйте Terraform:
    ```sh
    terraform init -backend-config="bucket=terraform-state-bucket-имя_вашего_проекта_в_GCP"
    ```
3. Примените конфигурацию:
    ```sh
    terraform apply
    ```