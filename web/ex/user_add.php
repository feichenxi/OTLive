<?php
require("../data/class.php");

$id = isset($_GET['id']) ? intval($_GET['id']) : 0;
$user = null;
$is_edit = false;

if ($id > 0) {
    $user = Table_Info("users", "alldata", "id='$id'");
    if ($user) {
        $is_edit = true;
    }
}

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $id = intval($_POST['id'] ?? 0);
    $nickname = mysqli_real_escape_string($conn, $_POST['nickname']);
    $phone = mysqli_real_escape_string($conn, $_POST['phone']);
    $real_name = mysqli_real_escape_string($conn, $_POST['real_name']);
    $balance = floatval($_POST['balance']);
    $points = intval($_POST['points']);
    $status = intval($_POST['status']);
    
    if (empty($nickname)) {
        echo "<script>alert('请输入昵称');</script>";
        goto show_form;
    }
    
    if ($id > 0) {
        $sql = "UPDATE users SET nickname='$nickname', phone='$phone', real_name='$real_name', balance='$balance', points='$points', status='$status' WHERE id='$id'";
    } else {
        $sql = "INSERT INTO users (nickname, phone, real_name, balance, points, status, create_time) VALUES ('$nickname', '$phone', '$real_name', '$balance', '$points', '$status', NOW())";
    }
    
    if (mysqli_query($conn, $sql)) {
        echo "<script>parent.layer.closeAll();parent.layui.table.reload('data-table');</script>";
    } else {
        echo "<script>alert('保存失败：" . mysqli_error($conn) . "');</script>";
    }
    exit;
}

show_form:
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title><?php echo $is_edit ? '编辑用户' : '添加用户'; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>
<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-body">
            <form class="layui-form" lay-filter="userForm" action="" method="post">
                <input type="hidden" name="id" value="<?php echo $id; ?>">
                
                <div class="layui-form-item">
                    <label class="layui-form-label">昵称</label>
                    <div class="layui-input-inline" style="width: 250px;">
                        <input type="text" name="nickname" lay-verify="required" placeholder="请输入昵称" autocomplete="off" class="layui-input" value="<?php echo $user ? htmlspecialchars($user['nickname']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">手机号</label>
                    <div class="layui-input-inline" style="width: 250px;">
                        <input type="text" name="phone" placeholder="请输入手机号" autocomplete="off" class="layui-input" value="<?php echo $user ? htmlspecialchars($user['phone']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">真实姓名</label>
                    <div class="layui-input-inline" style="width: 250px;">
                        <input type="text" name="real_name" placeholder="请输入真实姓名" autocomplete="off" class="layui-input" value="<?php echo $user ? htmlspecialchars($user['real_name']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">余额</label>
                    <div class="layui-input-inline" style="width: 150px;">
                        <input type="number" name="balance" step="0.01" placeholder="余额" autocomplete="off" class="layui-input" value="<?php echo $user ? $user['balance'] : '0'; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">积分</label>
                    <div class="layui-input-inline" style="width: 150px;">
                        <input type="number" name="points" placeholder="积分" autocomplete="off" class="layui-input" value="<?php echo $user ? $user['points'] : '0'; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">状态</label>
                    <div class="layui-input-inline" style="width: 150px;">
                        <select name="status" lay-verify="required">
                            <option value="1" <?php echo (!$user || $user['status'] == 1) ? 'selected' : ''; ?>>正常</option>
                            <option value="0" <?php echo ($user && $user['status'] == 0) ? 'selected' : ''; ?>>禁用</option>
                        </select>
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <div class="layui-input-block">
                        <button class="layui-btn" lay-submit lay-filter="saveBtn">立即提交</button>
                        <button type="button" class="layui-btn layui-btn-primary" onclick="closeLayer()">取消</button>
                    </div>
                </div>
            </form>
        </div>
    </div>
</div>

<script src="../public/layui/layui.js"></script>
<script>
layui.config({
    base: '../public/'
}).use(['form', 'layer'], function(){
    var form = layui.form
    ,layer = layui.layer
    ,$ = layui.$;
    
    // 关闭弹窗
    window.closeLayer = function() {
        parent.layer.close(parent.layer.getFrameIndex(window.name));
    };
    
    form.render();
});
</script>
</body>
</html>
