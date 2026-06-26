<?php
require("../data/class.php");

$id = isset($_GET['id']) ? intval($_GET['id']) : 0;
$wx = null;
$is_edit = false;

if ($id > 0) {
    $wx = Table_Info("wx_a16", "alldata", "id='$id'");
    if ($wx) {
        $is_edit = true;
    }
}

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $wxid = mysqli_real_escape_string($conn, $_POST['wxid']);
    $password = mysqli_real_escape_string($conn, $_POST['password']);
    $a16 = mysqli_real_escape_string($conn, $_POST['a16']);
    $proxy = mysqli_real_escape_string($conn, $_POST['proxy']);
    $status = intval($_POST['status']);
    $remarks = mysqli_real_escape_string($conn, $_POST['remarks']);
    
    if ($id > 0) {
        $sql = "UPDATE wx_a16 SET wxid='$wxid', password='$password', a16='$a16', proxy='$proxy', status='$status', remarks='$remarks' WHERE id='$id'";
    } else {
        $sql = "INSERT INTO wx_a16 (wxid, password, a16, proxy, status, remarks) VALUES ('$wxid', '$password', '$a16', '$proxy', '$status', '$remarks')";
    }
    
    if (mysqli_query($conn, $sql)) {
        echo "<script>parent.layer.closeAll();parent.layui.table.reload('data-table');</script>";
    } else {
        echo "<script>alert('保存失败：" . mysqli_error($conn) . "');</script>";
    }
    exit;
}
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title><?php echo $is_edit ? '编辑微信' : '添加微信'; ?></title>
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
            <form class="layui-form" lay-filter="wxForm" action="" method="post">
                
                <div class="layui-form-item">
                    <label class="layui-form-label">微信ID</label>
                    <div class="layui-input-block">
                        <input type="text" name="wxid" lay-verify="required" placeholder="请输入微信ID" autocomplete="off" class="layui-input" value="<?php echo $wx ? htmlspecialchars($wx['wxid']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">密码</label>
                    <div class="layui-input-block">
                        <input type="text" name="password" lay-verify="required" placeholder="请输入密码" autocomplete="off" class="layui-input" value="<?php echo $wx ? htmlspecialchars($wx['password']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">A16</label>
                    <div class="layui-input-block">
                        <input type="text" name="a16" lay-verify="required" placeholder="请输入A16" autocomplete="off" class="layui-input" value="<?php echo $wx ? htmlspecialchars($wx['a16']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">代理</label>
                    <div class="layui-input-block">
                        <input type="text" name="proxy" placeholder="请输入代理地址（可留空）" autocomplete="off" class="layui-input" value="<?php echo $wx ? htmlspecialchars($wx['proxy']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">状态</label>
                    <div class="layui-input-block">
                        <select name="status" lay-verify="required">
                            <option value="-1" <?php echo $wx && $wx['status'] == -1 ? 'selected' : ''; ?>>禁用</option>
                            <option value="0" <?php echo !$wx || $wx['status'] == 0 ? 'selected' : ''; ?>>启用</option>
                        </select>
                    </div>
                </div>
                
                <div class="layui-form-item layui-form-text">
                    <label class="layui-form-label">备注</label>
                    <div class="layui-input-block">
                        <textarea name="remarks" placeholder="请输入备注" class="layui-textarea"><?php echo $wx ? htmlspecialchars($wx['remarks']) : ''; ?></textarea>
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <div class="layui-input-block">
                        <button class="layui-btn" lay-submit lay-filter="saveBtn">立即提交</button>
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
    ,layer = layui.layer;
    
    form.render();
});
</script>
</body>
</html>
