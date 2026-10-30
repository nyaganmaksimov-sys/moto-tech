package ru.mototech.service

import android.app.Activity
import android.app.AlertDialog
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/** Native APK update checks. Actual APK releases must share the same signing certificate. */
class UpdateManager(private val activity:Activity) {
 private val api="https://api.github.com/repos/nyaganmaksimov-sys/moto-tech/releases/latest"
 private val manager by lazy {activity.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager}
 private var pendingDownload:Long?=null
 private var receiver:BroadcastReceiver?=null
 private var apkUri:Uri?=null

 fun check(manual:Boolean=false) {
  thread {
   try {
    val conn=URL(api).openConnection() as HttpURLConnection
    conn.connectTimeout=10000;conn.readTimeout=10000
    conn.setRequestProperty("Accept","application/vnd.github+json")
    conn.setRequestProperty("User-Agent","MOTO-TECH-Android")
    val body=conn.inputStream.bufferedReader().use {it.readText()}
    conn.disconnect()
    val release=JSONObject(body)
    if(release.optBoolean("draft")||release.optBoolean("prerelease"))return@thread
    val version=release.optString("tag_name").removePrefix("v")
    val local=activity.packageManager.getPackageInfo(activity.packageName,0).versionName?:"0.0.0"
    val assets=release.getJSONArray("assets")
    var link:String?=null
    for(i in 0 until assets.length()){
     val asset=assets.getJSONObject(i)
     val name=asset.optString("name")
     val url=asset.optString("browser_download_url")
     if(name.endsWith(".apk",true)&&name.contains("android",true)&&url.startsWith("https://github.com/nyaganmaksimov-sys/moto-tech/releases/download/")){
      link=url;break
     }
    }
    val download=link
    activity.runOnUiThread {
     if(compare(version,local)>0&&download!=null){
      if(pendingDownload==null){
       Toast.makeText(activity,"MOTO TECH $version: загрузка обновления началась",Toast.LENGTH_LONG).show()
       startDownload(download)
      }else if(manual) Toast.makeText(activity,"Обновление уже загружается",Toast.LENGTH_SHORT).show()
     } else if(manual) Toast.makeText(activity,"Новых обновлений нет",Toast.LENGTH_SHORT).show()
    }
   }catch(e:Exception){
    if(manual)activity.runOnUiThread{Toast.makeText(activity,"Не удалось проверить обновления",Toast.LENGTH_LONG).show()}
   }
  }
 }
 private fun compare(a:String,b:String):Int {
  val x=a.split('.').map{it.toIntOrNull()?:0};val y=b.split('.').map{it.toIntOrNull()?:0}
  for(i in 0 until maxOf(x.size,y.size)){val d=(x.getOrElse(i){0}).compareTo(y.getOrElse(i){0});if(d!=0)return d}
  return 0
 }
 private fun startDownload(link:String){
  val request=DownloadManager.Request(Uri.parse(link))
    .setTitle("MOTO TECH — обновление")
    .setDescription("Загрузка установочного APK")
    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
    .setDestinationInExternalFilesDir(activity,Environment.DIRECTORY_DOWNLOADS,"moto-tech-update.apk")
    .setAllowedOverMetered(true)
  pendingDownload=manager.enqueue(request)
  if(receiver==null){
   receiver=object:BroadcastReceiver(){
    override fun onReceive(context:Context?,intent:Intent?){
     if(intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID,-1L)!=pendingDownload)return
     val query=DownloadManager.Query().setFilterById(pendingDownload!!)
     manager.query(query)?.use {cursor->
      if(cursor.moveToFirst() && cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))==DownloadManager.STATUS_SUCCESSFUL){
       apkUri=manager.getUriForDownloadedFile(pendingDownload!!)
       activity.runOnUiThread{promptInstall()}
      }else activity.runOnUiThread{Toast.makeText(activity,"Ошибка загрузки APK",Toast.LENGTH_LONG).show()}
     }
    }
   }
   val filter=IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE)
   if(Build.VERSION.SDK_INT>=33) activity.registerReceiver(receiver,filter,Context.RECEIVER_EXPORTED)
   else @Suppress("DEPRECATION") activity.registerReceiver(receiver,filter)
  }
 }
 fun promptInstall(){
  val uri=apkUri?:return
  if(Build.VERSION.SDK_INT>=26 && !activity.packageManager.canRequestPackageInstalls()){
   AlertDialog.Builder(activity).setTitle("Разрешение на установку")
    .setMessage("Android требует разрешить установку обновлений из MOTO TECH. После разрешения вернитесь в приложение.")
    .setPositiveButton("Открыть настройки"){_,_->
     activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+activity.packageName)))
    }.setNegativeButton("Позже",null).show()
   return
  }
  AlertDialog.Builder(activity).setTitle("Обновление загружено")
   .setMessage("Установить обновление поверх текущей версии? Сохраните изменения в заказах.")
   .setPositiveButton("Установить"){_,_->
    val intent=Intent(Intent.ACTION_VIEW).apply {
     setDataAndType(uri,"application/vnd.android.package-archive")
     addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    try{activity.startActivity(intent)}catch(e:Exception){Toast.makeText(activity,"Не удалось открыть установщик",Toast.LENGTH_LONG).show()}
   }.setNegativeButton("Позже",null).show()
 }
 fun dispose(){
  receiver?.let {try{activity.unregisterReceiver(it)}catch(_:Exception){}}
  receiver=null
 }
}
