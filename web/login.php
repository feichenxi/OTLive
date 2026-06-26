<?php $login="no";require("data/class.php");?>
<?php
$hostname = $_SERVER['HTTP_HOST'];
if (filter_var($hostname, FILTER_VALIDATE_IP)) {
	print '对不起，未发现程序！';
	exit;
}

$t=$_GET['t'] ?? '';
if ($t=="checkcode")
{
	function captcha2($num=4,$size=20, $height=0,$width=0)
	{   
        !$width && $width = $num*$size*4/5+5;   
        !$height && $height = $size + 10;   
        $str = "1234567890123456789012345678901234567890";   
        $code = '';   
        for ($i=0; $i<$num; $i++){   
                $code.= $str[mt_rand(0, strlen($str)-1)];   
        }   
		$_SESSION["mcode"]=$code;//将验证码写入SESSION

        $im = imagecreatetruecolor($width,$height);   
        // 定义要用到的颜色   
        $back_color = imagecolorallocate($im, 235, 236, 237);   
        $boer_color = imagecolorallocate($im, 0,150,136);   
        $text_color = imagecolorallocate($im, mt_rand(0,200), mt_rand(0,120), mt_rand(0,120));   
           
        // 画背景   
        imagefilledrectangle($im,0,0,$width,$height,$back_color);   
        // 画边框   
        imagerectangle($im,0,0,$width-1,$height-1,$boer_color);   
        // 画干扰线   
        for($i=0;$i<5;$i++){   
            $font_color = imagecolorallocate($im, mt_rand(0,255), mt_rand(0,255), mt_rand(0,255));   
            imagearc($im,mt_rand(-$width,$width),mt_rand(-$height,$height),mt_rand(30,$width*2),mt_rand(20,$height*2),mt_rand(0,360),mt_rand(0,360),$font_color);   
        }   
        // 画干扰点   
        for($i=0;$i<50;$i++){   
                $font_color = imagecolorallocate($im, mt_rand(0,255), mt_rand(0,255), mt_rand(0,255));   
                imagesetpixel($im,mt_rand(0,$width),mt_rand(0,$height),$font_color);   
        }   
        // 画验证码   
        @imagefttext($im, $size , 0, 11, $size+3, $text_color, 'public/font/simhei.ttf',$code);   
        header("Cache-Control: max-age=1, s-maxage=1, no-cache, must-revalidate");   
        header("Content-type: image/png");   
        imagepng($im);
        imagedestroy($im);
    }
	
	captcha2(4,30,38,100);
	exit;
}

// Check for error messages
$error_message = '';
if ($t=="pass") {
    $error_message = 'User name or password error.';
} else if ($t=="code") {
    $error_message = 'Verification code error';
} else if ($t=="logout") {
    // 处理退出登录逻辑
    // 清除所有会话变量
    $_SESSION = array();

    // 删除会话cookie
    if (ini_get("session.use_cookies")) {
        $params = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000,
            $params["path"], $params["domain"],
            $params["secure"], $params["httponly"]
        );
    }

    // 删除记住登录的cookie
    setcookie('admin_remember', '', time() - 3600, '/', '', false, true);
    
    // 销毁会话
    session_destroy();
    
    $error_message = 'You have successfully logged out.';
}

if ($t=="login")
{
	// 检查数据库连接
	if (!isset($_ENV['conn']) || $_ENV['conn'] === null) {
		print '<script>alert("数据库连接失败，请检查数据库配置。");window.location="login.php";</script>';
		exit;
	}
	
	$username=$_POST['username'];
	$input_password=$_POST['password'];
	
	// 使用 plain MD5
	$password = md5($input_password);
	
	$vcode=$_POST['vcode'];
	$mcode=$_SESSION['mcode'];
	
	// 获取记住登录状态的选项
	$remember_login = isset($_POST['remember_login']) ? true : false;
	
	if ($vcode==$mcode)
	{
		// 构建SQL查询，只检查 plain MD5
		$sql="SELECT * FROM admin WHERE username='$username' AND password='$password' limit 1";	
		
		$result=mysqli_query($_ENV['conn'],$sql);
		$row=mysqli_fetch_array($result);
		if ($row['id'])
		{
			$_SESSION['admin_id']=$row['id'];
			if($username=='admin') {
                $_SESSION['store_id']=1;
            } else {
                $_SESSION['store_id']=$row['id'];
            }
			
			$_ENV['login_id']=$row['id'];
			$_SESSION['username']=$username;
			$_SESSION['power']=$row['power'];
			$_SESSION['admin_username']=$row['name'];
			
			// 如果用户选择了记住登录状态30天
			if ($remember_login) {
				// 创建一个包含用户ID和登录时间的数组
				$cookie_data = array(
					'user_id' => $row['id'],
					'login_time' => time()
				);
				
				// 将数组序列化并加密，最后进行base64编码
				$cookie_value = base64_encode(EncryptStr(serialize($cookie_data)));
				
				// 设置COOKIE，有效期30天
				setcookie('admin_remember', $cookie_value, time() + (30 * 24 * 60 * 60), '/', '', false, true);
			}
			
			print "<script>window.location='index.php';</script>";
			exit;
		}
		else
		{
			// 调试信息 - 仅在开发环境中使用，生产环境中应删除
			// error_log("Login failed for user: $username. SQL: $sql");
			print '<script>window.location="login.php?t=pass";</script>';
			exit;
		}
	}
	else
	{
		print '<script>window.location="login.php?t=code";</script>';
		exit;
	}
}


?>

<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
	<title>Login - <?php print $setting['app_name'];?></title>
	<meta name="renderer" content="webkit">
	<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
	<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
	<link rel="stylesheet" href="public/layui/css/layui.css" media="all">
	<link rel="stylesheet" href="public/style/admin.css" media="all">
	<link rel="stylesheet" href="public/style/login.css" media="all">
    <style>
        #LAY-user-login {
            background: url(img/loginbg.jpg) no-repeat center center fixed;
            background-size: cover;
            display: flex !important;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 0 0 50px 0;
        }
        .layadmin-user-login-header h2 {
            color: #ffffff;
        }
    </style>
</head>
<body>

  <div class="layadmin-user-login layadmin-user-display-show" id="LAY-user-login" style="display: none;">

    <div class="layadmin-user-login-main">
      <div class="layadmin-user-login-box layadmin-user-login-header">
        <h2><?php print $setting['app_name'];?></h2>
        <p>Professionalism, concentration and concentration</p>
      </div>
      
      <?php if ($error_message): ?>
      <div class="layui-form-item">
          <div class="layui-card" style="margin: 0 20px 20px; padding: 10px; background-color: #fff3f3; border: 1px solid #ffe6e6; color: #ff5722;">
              <div class="layui-card-body" style="padding: 10px;">
                  <?php echo $error_message; ?>
              </div>
          </div>
      </div>
      <?php endif; ?>
      
      <div class="layadmin-user-login-box layadmin-user-login-body layui-form">
        <form action="?t=login" enctype="multipart/form-data" method="post">
            <div class="layui-form-item">
              <label class="layadmin-user-login-icon layui-icon layui-icon-username" for="LAY-user-login-username"></label>
              <input type="text" name="username" id="LAY-user-login-username" lay-verify="required" placeholder="UserName" class="layui-input">
            </div>
            <div class="layui-form-item">
              <label class="layadmin-user-login-icon layui-icon layui-icon-password" for="LAY-user-login-password"></label>
              <input type="password" name="password" id="LAY-user-login-password" lay-verify="required" placeholder="PassWord" class="layui-input">
            </div>
            <div class="layui-form-item">
              <div class="layui-row">
                <div class="layui-col-xs7">
                  <label class="layadmin-user-login-icon layui-icon layui-icon-vercode" for="LAY-user-login-vercode"></label>
                  <input type="text" name="vcode" id="LAY-user-login-vercode" lay-verify="required" placeholder="VerCode" class="layui-input">
                </div>
                <div class="layui-col-xs5">
                  <div style="margin-left: 10px;">
                    <img id="checkpic" onclick="changing();" src="?t=checkcode" class="layadmin-user-login-codeimg">
                  </div>
                </div>
              </div>
            </div>
            <div class="layui-form-item" style="margin-bottom: 20px;">
              <input type="checkbox" name="remember_login" lay-skin="primary" title="Keep logged.">
              <a href="javascript:;" onclick="layui.layer.msg('Please contact your technical service provider.');" class="layadmin-user-jump-change layadmin-link" style="margin-top: 7px;">Forgot password?</a>
            </div>
            <div class="layui-form-item">
              <button class="layui-btn layui-btn-fluid" lay-submit lay-filter="LAY-user-login-submit">Login</button>
            </div>
        </form>
      </div>
    </div>
    
    <div class="layui-trans layadmin-user-login-footer">
      <p>© 2025 Background management system</p>
    </div>

  </div>

  <script src="public/layui/layui.js"></script>  
  <script>
  layui.config({
    base: 'public/'
  }).extend({
    index: 'lib/index'
  }).use(['index', 'form'], function(){
    var $ = layui.$
    ,form = layui.form;
    
   
    $('#LAY-user-login').show();
    
  
    window.changing = function() {
        document.getElementById('checkpic').src = "?t=checkcode&" + Math.random();
    }
    
   
    form.on('submit(LAY-user-login-submit)', function(obj){
      return true;
    });
  });
  </script>

</body>
</html>