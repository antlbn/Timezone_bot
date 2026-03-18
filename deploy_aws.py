import boto3
import sys

# --- ПОДГОТОВКА ---
# 1. Зарегайся на AWS и получи Access Key / Secret Key.
# 2. Установи библиотеку: pip install boto3
# 3. Настрой доступ: aws configure (введи ключи и регион, например us-east-1)
# 4. Впиши свои токены в ENV_CONTENT ниже.
# 5. Запусти: python deploy_aws.py

# --- CONFIGURATION ---
REGION = "us-east-1"      
INSTANCE_TYPE = "t3.micro" 
REPO_URL = "https://github.com/YOUR_USERNAME/Timezone_bot.git" 
KEY_NAME = "timezone-bot-key" # Скрипт сам создаст этот ключ и сохранит его рядом

# Вставь содержимое своего .env файла
ENV_CONTENT = """
TELEGRAM_TOKEN=your_telegram_token
DISCORD_TOKEN=your_discord_token
OPENAI_API_KEY=your_openai_key
"""

# --- USER DATA (CLOUD-INIT) ---
# This script runs automatically on the first server boot.
USER_DATA_TEMPLATE = f"""#!/bin/bash
set -e

# 1. Update and install basic tools
apt-get update
apt-get install -y git python3-pip curl

# 2. Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# 3. Clone repository
mkdir -p /opt/timezone-bot
git clone {REPO_URL} /opt/timezone-bot
cd /opt/timezone-bot

# 4. Create .env file from template
cat <<EOF > .env
{ENV_CONTENT}
EOF

# 5. Build environment and install dependencies
/root/.cargo/bin/uv sync

# 6. Create systemd service for Telegram bot
cat <<EOF > /etc/systemd/system/tz-telegram.service
[Unit]
Description=Timezone Bot - Telegram
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/timezone-bot
ExecStart=/root/.cargo/bin/uv run python -m src.main
Restart=always
EnvFile=/opt/timezone-bot/.env

[Install]
WantedBy=multi-user.target
EOF

# 7. Start the service
systemctl daemon-reload
systemctl enable tz-telegram
systemctl start tz-telegram

echo "Deployment complete!"
"""

def deploy():
    # Создаем клиент EC2
    try:
        ec2 = boto3.client('ec2', region_name=REGION)
    except Exception as e:
        print(f"Ошибка инициализации AWS: {e}\nУбедись, что выполнил 'aws configure' и ввел ACCESS_KEY/SECRET_KEY")
        return

    print(f"--- Деплой Timezone Bot в регионе {REGION} ---")

    # 1. Создаем/проверяем SSH ключ
    print(f"Настройка SSH ключа ({KEY_NAME})...")
    key_file = f"{KEY_NAME}.pem"
    try:
        # Пытаемся создать новый ключ
        key_pair = ec2.create_key_pair(KeyName=KEY_NAME)
        with open(key_file, "w") as f:
            f.write(key_pair['KeyMaterial'])
        # Права доступа (только для владельца) — важно для SSH
        if sys.platform != "win32":
            os.chmod(key_file, 0o400)
        print(f"Создан новый ключ и сохранен в: {key_file}")
    except Exception as e:
        if 'InvalidKeyPair.Duplicate' in str(e):
            if os.path.exists(key_file):
                print(f"Используем существующий локальный ключ: {key_file}")
            else:
                print(f"Ключ '{KEY_NAME}' уже есть в AWS, но нет файла '{key_file}'.")
                print("СОВЕТ: Или удали ключ в панели AWS (EC2 -> Key Pairs), или найди старый .pem файл.")
                return
        else:
            print(f"Ошибка с ключом: {e}")
            return

    # 2. Создаем Security Group (если её еще нет)
    sg_name = "timezone-bot-sg"
    try:
        print("Настройка прав доступа (Security Group)...")
        sg = ec2.create_security_group(
            GroupName=sg_name,
            Description="Allow SSH and default outbound"
        )
        sg_id = sg['GroupId']
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpProtocol='tcp',
            FromPort=22,
            ToPort=22,
            CidrIp='0.0.0.0/0' 
        )
    except Exception as e:
        if 'InvalidGroup.Duplicate' in str(e):
            response = ec2.describe_security_groups(GroupNames=[sg_name])
            sg_id = response['SecurityGroups'][0]['GroupId']
            print(f"Security Group уже существует: {sg_id}")
        else:
            print(f"Ошибка SG: {e}")
            return

    # 3. Ищем образ Ubuntu 22.04 LTS
    print("Поиск образа (AMI) Ubuntu 22.04...")
    ami_response = ec2.describe_images(
        Filters=[
            {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']},
            {'Name': 'state', 'Values': ['available']}
        ],
        Owners=['099720109477']
    )
    ami_id = sorted(ami_response['Images'], key=lambda x: x['CreationDate'], reverse=True)[0]['ImageId']

    # 4. Запускаем инстанс
    print(f"Запуск сервера (AMI: {ami_id})...")
    instance = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        KeyName=KEY_NAME,  # Используем наш ключ
        SecurityGroupIds=[sg_id],
        UserData=USER_DATA_TEMPLATE,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'TimezoneBot-Server'}]
        }]
    )
    
    instance_id = instance['Instances'][0]['InstanceId']
    print(f"Сервер {instance_id} создается.")

    # 5. Ожидаем готовности
    print("Ожидание запуска (может занять минуту)...")
    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = desc['Reservations'][0]['Instances'][0].get('PublicIpAddress')

    print("\n" + "!"*40)
    print("УСПЕХ! Сервер запущен.")
    print(f"Публичный IP: {public_ip}")
    print(f"Файл ключа:   {key_file}")
    print("!"*40)
    print(f"\nКоманда для входа: ssh -i {key_file} ubuntu@{public_ip}")
    print(f"Команда для логов: ssh -i {key_file} ubuntu@{public_ip} 'journalctl -u tz-telegram -f'")

if __name__ == "__main__":
    import os
    if REPO_URL == "https://github.com/YOUR_USERNAME/Timezone_bot.git":
        print("ОШИБКА: Сначала впиши свой REPO_URL в файл!")
        sys.exit(1)
    deploy()
