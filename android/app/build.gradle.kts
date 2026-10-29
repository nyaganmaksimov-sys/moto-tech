plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android { namespace = "ru.mototech.service"; compileSdk = 35
 defaultConfig { applicationId = "ru.mototech.service"; minSdk = 26; targetSdk = 35; versionCode = 3; versionName = "0.2.0" }
 buildTypes { release { isMinifyEnabled = false } }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
 kotlinOptions { jvmTarget = "17" }
}
