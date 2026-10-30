# Настройка постоянной подписи Android MOTO TECH

Ключ создаётся **один раз на вашем компьютере**. Не отправляйте файл .jks, пароли или base64 в чат и не добавляйте их в git.

## 1. Создать ключ на Windows
Нужен JDK (Android Studio -> встроенный JDK или установленный Java JDK). В PowerShell, из безопасной директории:

```powershell
keytool -genkeypair -v -keystore moto-tech-release.jks -alias moto-tech -keyalg RSA -keysize 3072 -validity 10000
```

Следуйте приглашениям keytool и сохраните пароль в менеджере паролей. Сохраните резервную копию `moto-tech-release.jks` в защищённом месте, отдельно от компьютера. Не используйте один и тот же пароль в других проектах.

## 2. Секреты GitHub
Откройте: https://github.com/nyaganmaksimov-sys/moto-tech/settings/secrets/actions

Создайте четыре **Repository secrets**:
- `MOTO_ANDROID_KEYSTORE_BASE64`: результат команды ниже (не публиковать)
- `MOTO_ANDROID_KEYSTORE_PASSWORD`: пароль .jks
- `MOTO_ANDROID_KEY_ALIAS`: `moto-tech`
- `MOTO_ANDROID_KEY_PASSWORD`: пароль ключа (если отдельный)

В PowerShell скопируйте base64 прямо в буфер (не печатая в общедоступные журналы):

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path .\moto-tech-release.jks))) | Set-Clipboard
```

Вставьте в поле секретного значения GitHub; после этого очистите буфер обмена.

## 3. Выпуск
GitHub Actions -> Android signed release -> Run workflow -> выберите `feature/android-app`. При успехе GitHub создаст Release v0.2.0 с подписанным APK. Тестовые APK из workflow Android test APK используют debug-подпись и не обновляются поверх release-подписанного приложения.

Проверяйте подпись и versionCode всех дальнейших релизов. Увеличивайте versionCode при любом новом APK. Сохраняйте оригинальный ключ подписи всегда: без него установка поверх старого релиза невозможна.

**Примечание:** GitHub Actions имеет доступ к секретам только после вашего добавления; ChatGPT не должен видеть, получать или хранить пароли/ключ.
