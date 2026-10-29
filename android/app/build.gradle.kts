plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
 namespace = "ru.mototech.service"
 compileSdk = 35
 defaultConfig { applicationId = "ru.mototech.service"; minSdk = 26; targetSdk = 35; versionCode = 3; versionName = "0.2.0" }
 signingConfigs {
  create("production") {
   storeFile = file(System.getenv("MOTO_KEYSTORE_PATH") ?: "release-signing-unconfigured.jks")
   storePassword = System.getenv("MOTO_KEYSTORE_PASSWORD")
   keyAlias = System.getenv("MOTO_KEY_ALIAS")
   keyPassword = System.getenv("MOTO_KEY_PASSWORD")
  }
 }
 buildTypes {
  getByName("release") {
   isMinifyEnabled = false
   signingConfig = signingConfigs.getByName("production")
  }
 }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
 kotlinOptions { jvmTarget = "17" }
}
