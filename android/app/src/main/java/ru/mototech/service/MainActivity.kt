package ru.mototech.service
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.*
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView

class MainActivity : Activity() {
 private val home="https://nyaganmaksimov-sys.github.io/moto-tech/workspace.html"
 private lateinit var web:WebView
 private lateinit var info:TextView
 private var fileCallback:ValueCallback<Array<Uri>>?=null
 private val fileRequest=3001
 @SuppressLint("SetJavaScriptEnabled")
 override fun onCreate(savedInstanceState:Bundle?) {
  super.onCreate(savedInstanceState)
  val layout=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setBackgroundColor(0xff101319.toInt())}
  val bar=ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal).apply{max=100}
  info=TextView(this).apply{setTextColor(0xfff5f5f5.toInt());text="MOTO TECH · подключение...";setPadding(12,8,12,8)}
  web=WebView(this)
  layout.addView(info);layout.addView(bar,LinearLayout.LayoutParams(-1,4))
  layout.addView(web,LinearLayout.LayoutParams(-1,0,1f))
  setContentView(layout)
  CookieManager.getInstance().setAcceptCookie(true)
  web.settings.javaScriptEnabled=true
  web.settings.domStorageEnabled=true
  web.settings.cacheMode=WebSettings.LOAD_DEFAULT
  web.settings.allowFileAccess=false
  web.settings.allowContentAccess=true
  web.webViewClient=object:WebViewClient(){
   override fun shouldOverrideUrlLoading(view:WebView?,request:WebResourceRequest):Boolean{
    val uri=request.url
    if(uri.scheme=="https" && uri.host=="nyaganmaksimov-sys.github.io" && uri.path?.startsWith("/moto-tech/")==true)return false
    if(uri.scheme=="https")startActivity(Intent(Intent.ACTION_VIEW,uri))
    return true
   }
   override fun onPageFinished(view:WebView?,url:String?){info.visibility=View.GONE}
   override fun onReceivedError(view:WebView?,request:WebResourceRequest?,error:WebResourceError?){
    if(request?.isForMainFrame==true){info.visibility=View.VISIBLE;info.text="Нет подключения к системе. Проверьте интернет."}
   }
  }
  web.webChromeClient=object:WebChromeClient(){
   override fun onProgressChanged(view:WebView?,progress:Int){bar.progress=progress;bar.visibility=if(progress==100)View.GONE else View.VISIBLE}
   override fun onShowFileChooser(webView:WebView?,cb:ValueCallback<Array<Uri>>?,params:FileChooserParams?):Boolean{
    fileCallback?.onReceiveValue(null);fileCallback=cb
    return try{startActivityForResult(params?.createIntent()?:Intent(Intent.ACTION_GET_CONTENT).apply{type="image/*";addCategory(Intent.CATEGORY_OPENABLE)},fileRequest);true}
    catch(e:Exception){fileCallback=null;cb?.onReceiveValue(null);false}
   }
  }
  web.loadUrl(home)
 }
 @Deprecated("Deprecated in Java")
 override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?){
  super.onActivityResult(requestCode,resultCode,data)
  if(requestCode==fileRequest){fileCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode,data));fileCallback=null}
 }
 @Deprecated("Deprecated in Java")
 override fun onBackPressed(){if(web.canGoBack())web.goBack() else super.onBackPressed()}
 override fun onDestroy(){web.destroy();super.onDestroy()}
}
