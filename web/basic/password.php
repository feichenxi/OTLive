<?php 
require("../data/class.php");
?>
<?php
$t = isset($_GET['t']) ? $_GET['t'] : '';
if ($t=="save") {
    // Check if it's an AJAX request
    $is_ajax = !empty($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) == 'xmlhttprequest';
    
	$user_id = $_SESSION['admin_id'];
	$username = $_SESSION['username'];
	$oldPassword = $_POST['oldPassword'];
	$password = $_POST['password'];
	$repassword = $_POST['repassword'];
    
    // Validate input
    if (empty($oldPassword)) {
        $error = '请输入当前密码';
    } else if (empty($password)) {
        $error = '请输入新密码';
    } else if ($password !== $repassword) {
        $error = '两次输入的新密码不一致';
    } else {
        // Get current user info
        $sql_power = "SELECT * FROM admin WHERE id=$user_id";
        $que_power = mysqli_query($conn, $sql_power);
        $list_power = mysqli_fetch_array($que_power);
        
        if (!$list_power) {
            $error = '用户信息不存在';
        } else {
            // Check old password using plain MD5
            if ($list_power['password'] != md5($oldPassword)) {
                $error = '当前密码输入不正确';
            } else {
                // Hash new password using plain MD5
                $newPassword = md5($password);
                $sql = "UPDATE admin SET password='$newPassword' WHERE id=$user_id";
                $que = mysqli_query($conn, $sql);
                
                if ($que) {
                    $success = '密码修改成功';
                } else {
                    $error = '密码修改失败，请稍后重试';
                }
            }
        }
    }
    
    // Return JSON response for AJAX requests
    if ($is_ajax) {
        header('Content-Type: application/json');
        if (isset($success)) {
            echo json_encode(['code' => 0, 'msg' => $success]);
        } else {
            echo json_encode(['code' => 1, 'msg' => $error]);
        }
        exit;
    }
    
    // For non-AJAX requests, set message to be displayed
    if (isset($success)) {
        $message = $success;
        $message_type = 'success';
    } else {
        $message = $error;
        $message_type = 'error';
    }
}
?>
<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
    <meta name="renderer" content="webkit">
	<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
	<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
	<link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
    <title>修改密码</title>
</head>
<body>

  <div class="layui-fluid">
    <div class="layui-row layui-col-space15">
      <div class="layui-col-md12">
        <div class="layui-card">
          <div class="layui-card-header">修改密码</div>
          <div class="layui-card-body" pad15>
          <?php if (isset($message)): ?>
            <div class="layui-form-item">
                <div class="layui-card" style="margin: 0 0 20px; padding: 10px; background-color: <?php echo $message_type == 'success' ? '#f3fff3' : '#fff3f3'; ?>; border: 1px solid <?php echo $message_type == 'success' ? '#e6ffe6' : '#ffe6e6'; ?>; color: <?php echo $message_type == 'success' ? '#22ff22' : '#ff5722'; ?>;">
                    <div class="layui-card-body" style="padding: 10px;">
                        <?php echo $message; ?>
                    </div>
                </div>
            </div>
          <?php endif; ?>
          <form action="?t=save" class="layui-form" method="post">
            
            <div class="layui-form" lay-filter="">
              <div class="layui-form-item">
                <label class="layui-form-label">当前密码</label>
                <div class="layui-input-inline">
                  <input type="password" name="oldPassword" lay-verify="required" class="layui-input">
                </div>
              </div>
              <div class="layui-form-item">
                <label class="layui-form-label">新密码</label>
                <div class="layui-input-inline">
                  <input type="password" name="password" lay-verify="required" lay-verType="tips" autocomplete="off" id="LAY_password" class="layui-input">
                </div>
              </div>
              <div class="layui-form-item">
                <label class="layui-form-label">确认新密码</label>
                <div class="layui-input-inline">
                  <input type="password" name="repassword" lay-verify="required" lay-verType="tips" autocomplete="off" class="layui-input">
                </div>
              </div>
              <div class="layui-form-item">
                <div class="layui-input-block">
                  <button class="layui-btn" lay-submit lay-filter="setmypass">确认修改</button>
                </div>
              </div>
            </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>

  
  <script src="../public/layui/layui.js"></script>
  <script>
  layui.config({
    base: '../public/' //静态资源所在路径
  }).use(['form', 'layer'], function(){
    var $ = layui.$
    ,form = layui.form
    ,layer = layui.layer;
    
    //监听提交
    form.on('submit(setmypass)', function(data){
        $.ajax({
            url: '?t=save',
            type: 'POST',
            data: data.field,
            dataType: 'json',
            success: function(res){
                if(res.code === 0){
                    layer.msg(res.msg, {icon: 1});
                    // Clear form fields
                    $('input[type=password]').val('');
                } else {
                    layer.msg(res.msg, {icon: 2});
                }
            },
            error: function(){
                layer.msg('请求失败', {icon: 2});
            }
        });
        return false; //阻止表单跳转
    });
  });
  </script>
</body>
</html>