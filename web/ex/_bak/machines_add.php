<?php
require("../data/class.php");

$id = isset($_GET['id']) ? intval($_GET['id']) : 0;
$machine = null;
$is_edit = false;

if ($id > 0) {
    $machine = Table_Info("machines", "alldata", "id='$id'");
    if ($machine) {
        $is_edit = true;
    }
}

$machines_sql = "SELECT id, machine FROM machines ORDER BY id ASC";
$machines_result = mysqli_query($conn, $machines_sql);
$machines = array();
while($row = mysqli_fetch_assoc($machines_result)) {
    $machines[] = $row;
}

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $machine_name = mysqli_real_escape_string($conn, $_POST['machine']);
    $ip = mysqli_real_escape_string($conn, $_POST['ip']);
    $proxy = isset($_POST['proxy']) ? trim($_POST['proxy']) : '';
    $time_login = isset($_POST['time_login']) ? trim($_POST['time_login']) : '';
    $time_buy = isset($_POST['time_buy']) ? trim($_POST['time_buy']) : '';
    $num_login = intval($_POST['num_login']);
    $remarks = mysqli_real_escape_string($conn, $_POST['remarks']);
    
    $proxy_sql = !empty($proxy) ? "'$proxy'" : "''";
    $time_login_sql = !empty($time_login) ? "'$time_login'" : "''";
    $time_buy_sql = !empty($time_buy) ? "'$time_buy'" : "''";
    
    if ($id > 0) {
        $sql = "UPDATE machines SET machine='$machine_name', ip='$ip', proxy=$proxy_sql, time_login=$time_login_sql, time_buy=$time_buy_sql, num_login='$num_login', remarks='$remarks' WHERE id='$id'";
    } else {
        $sql = "INSERT INTO machines (machine, ip, proxy, time_login, time_buy, num_login, remarks) VALUES ('$machine_name', '$ip', $proxy_sql, $time_login_sql, $time_buy_sql, '$num_login', '$remarks')";
		print $sql;
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
    <title><?php echo $is_edit ? '编辑运行机' : '添加运行机'; ?></title>
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
            <form class="layui-form" lay-filter="machineForm" action="" method="post">
                
                <div class="layui-form-item">
                    <label class="layui-form-label">机器名称</label>
                    <div class="layui-input-inline" style="width: 170px;">
                        <input type="text" name="machine" lay-verify="required" placeholder="请输入机器名称" autocomplete="off" class="layui-input" value="<?php echo $machine ? htmlspecialchars($machine['machine']) : ''; ?>">
                    </div>
                    <label class="layui-form-label">地区</label>
                    <div class="layui-input-inline" style="width: 170px;">
                        <input type="text" name="ip" lay-verify="required" placeholder="请输入地区" autocomplete="off" class="layui-input" value="<?php echo $machine ? htmlspecialchars($machine['ip']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
					<label class="layui-form-label">登录账号数</label>
                    <div class="layui-input-inline" style="width: 170px;">
                        <input type="number" name="num_login" lay-verify="required" placeholder="请输入登录账号数" autocomplete="off" class="layui-input" value="<?php echo $machine ? intval($machine['num_login']) : '100'; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">登录时间</label>
                    <div class="layui-input-inline" style="width: 170px;">
                        <input type="text" name="time_login" id="time_login" placeholder="请选择登录时间" autocomplete="off" class="layui-input" value="<?php echo $machine && $machine['time_login'] ? htmlspecialchars($machine['time_login']) : '07:30:00'; ?>">
                    </div>
                    <label class="layui-form-label">查票时间</label>
                    <div class="layui-input-inline" style="width: 170px;">
                        <input type="text" name="time_buy" id="time_buy" placeholder="请选择查票时间" autocomplete="off" class="layui-input" value="<?php echo $machine && $machine['time_buy'] ? htmlspecialchars($machine['time_buy']) : '08:00:00'; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">代理IP</label>
                    <div class="layui-input-inline" style="width: 170px;">
                        <input type="text" name="proxy" placeholder="无代理时请留空" autocomplete="off" class="layui-input" value="<?php echo $machine ? htmlspecialchars($machine['proxy']) : ''; ?>">
                    </div>
                    <label class="layui-form-label">备注信息</label>
                    <div class="layui-input-inline" style="width: 170px;">
                        <input type="text" name="remarks" placeholder="请输入备注" autocomplete="off" class="layui-input" value="<?php echo $machine ? htmlspecialchars($machine['remarks']) : ''; ?>">
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
}).use(['form', 'layer', 'laydate'], function(){
    var form = layui.form
    ,layer = layui.layer
    ,laydate = layui.laydate;
    
    laydate.render({
        elem: '#time_login'
        ,type: 'time'
        ,format: 'HH:mm:ss'
        ,trigger: 'click'
    });
    
    laydate.render({
        elem: '#time_buy'
        ,type: 'time'
        ,format: 'HH:mm:ss'
        ,trigger: 'click'
    });
    
    form.render();
});
</script>
</body>
</html>
