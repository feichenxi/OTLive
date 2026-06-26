<?php
require("../data/class.php");

$id = isset($_GET['id']) ? intval($_GET['id']) : 0;
$guest = null;
$is_edit = false;

if ($id > 0) {
    $guest = Table_Info("guests", "alldata", "id='$id'");
    if ($guest) {
        $is_edit = true;
    }
}

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $group_name = mysqli_real_escape_string($conn, $_POST['group_name']);
    $phone = mysqli_real_escape_string($conn, $_POST['phone']);
    $ticket_date = mysqli_real_escape_string($conn, $_POST['ticket_date']);
    $ticket_time = mysqli_real_escape_string($conn, $_POST['ticket_time']);
    $status = intval($_POST['status']);
    $remarks = mysqli_real_escape_string($conn, $_POST['remarks']);
    $priority = intval($_POST['priority']);
    $order_wxid = mysqli_real_escape_string($conn, $_POST['order_wxid']);
    $reset_queue = isset($_POST['reset_queue']) ? 1 : 0;
    
    $name1 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['name1'])));
    $id_type1 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_type1'])));
    $id_num1 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_num1'])));
    $modelcode1 = mysqli_real_escape_string($conn, $_POST['modelcode1']);
    
    $name2 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['name2'])));
    $id_type2 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_type2'])));
    $id_num2 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_num2'])));
    $modelcode2 = mysqli_real_escape_string($conn, $_POST['modelcode2']);
    
    $name3 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['name3'])));
    $id_type3 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_type3'])));
    $id_num3 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_num3'])));
    $modelcode3 = mysqli_real_escape_string($conn, $_POST['modelcode3']);
    
    $name4 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['name4'])));
    $id_type4 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_type4'])));
    $id_num4 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_num4'])));
    $modelcode4 = mysqli_real_escape_string($conn, $_POST['modelcode4']);
    
    $name5 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['name5'])));
    $id_type5 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_type5'])));
    $id_num5 = mysqli_real_escape_string($conn, preg_replace('/\s+/', '', trim($_POST['id_num5'])));
    $modelcode5 = mysqli_real_escape_string($conn, $_POST['modelcode5']);
    
    $assigned_count = 0;
    
    if ($reset_queue) {
        $assigned_count = 0;
        $order_wxid = '';
        $status = 0;
    } elseif ($id > 0) {
        $assigned_count = $guest['assigned_count'];
    }
    
    if ($id > 0) {
        $sql = "UPDATE guests SET group_name='$group_name', phone='$phone', ticket_date='$ticket_date', ticket_time='$ticket_time', status='$status', remarks='$remarks', priority='$priority', order_wxid='$order_wxid', assigned_count='$assigned_count', name1='$name1', id_type1='$id_type1', id_num1='$id_num1', modelcode1='$modelcode1', name2='$name2', id_type2='$id_type2', id_num2='$id_num2', modelcode2='$modelcode2', name3='$name3', id_type3='$id_type3', id_num3='$id_num3', modelcode3='$modelcode3', name4='$name4', id_type4='$id_type4', id_num4='$id_num4', modelcode4='$modelcode4', name5='$name5', id_type5='$id_type5', id_num5='$id_num5', modelcode5='$modelcode5' WHERE id='$id'";
    } else {
        $assigned_count = 0;
        $sql = "INSERT INTO guests (group_name, phone, ticket_date, ticket_time, status, remarks, priority, order_wxid, assigned_count, name1, id_type1, id_num1, modelcode1, name2, id_type2, id_num2, modelcode2, name3, id_type3, id_num3, modelcode3, name4, id_type4, id_num4, modelcode4, name5, id_type5, id_num5, modelcode5) VALUES ('$group_name', '$phone', '$ticket_date', '$ticket_time', '$status', '$remarks', '$priority', '$order_wxid', '$assigned_count', '$name1', '$id_type1', '$id_num1', '$modelcode1', '$name2', '$id_type2', '$id_num2', '$modelcode2', '$name3', '$id_type3', '$id_num3', '$modelcode3', '$name4', '$id_type4', '$id_num4', '$modelcode4', '$name5', '$id_type5', '$id_num5', '$modelcode5')";
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
    <title><?php echo $is_edit ? '编辑客人' : '添加客人'; ?></title>
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
            <form class="layui-form" lay-filter="guestForm" action="" method="post">
                
                <?php for($i = 1; $i <= 5; $i++): ?>
                <div class="layui-form-item">
                    <label class="layui-form-label">第<?php echo $i; ?>人</label>
                    <div class="layui-input-inline" style="width: 100px;">
                        <input type="text" name="name<?php echo $i; ?>" placeholder="姓名" autocomplete="off" class="layui-input" value="<?php echo $guest ? htmlspecialchars($guest['name'.$i]) : ''; ?>">
                    </div>
                    <div class="layui-input-inline" style="width: 120px;">
                        <select name="id_type<?php echo $i; ?>" lay-verify="required">
                            <option value="0" <?php echo (!$guest || $guest['id_type'.$i] == '0') ? 'selected' : ''; ?>>身份证</option>
                            <option value="1" <?php echo $guest && $guest['id_type'.$i] == '1' ? 'selected' : ''; ?>>港澳居民来往内地通行证</option>
                            <option value="2" <?php echo $guest && $guest['id_type'.$i] == '2' ? 'selected' : ''; ?>>护照</option>
                            <option value="3" <?php echo $guest && $guest['id_type'.$i] == '3' ? 'selected' : ''; ?>>台湾居民来往大陆通行证</option>
                            <option value="4" <?php echo $guest && $guest['id_type'.$i] == '4' ? 'selected' : ''; ?>>港澳台居民身份件</option>
                            <option value="5" <?php echo $guest && $guest['id_type'.$i] == '5' ? 'selected' : ''; ?>>外国人永久居留身份证</option>
                        </select>
                    </div>
                    <div class="layui-input-inline" style="width: 190px;">
                        <input type="text" name="id_num<?php echo $i; ?>" placeholder="证件号" autocomplete="off" class="layui-input" value="<?php echo $guest ? htmlspecialchars($guest['id_num'.$i]) : ''; ?>">
                    </div>
                    <div class="layui-input-inline" style="width: 100px;">
                        <select name="modelcode<?php echo $i; ?>">
                            <option value="" <?php echo (!$guest || !$guest['modelcode'.$i]) ? 'selected' : ''; ?>>请选择</option>
                            <option value="MP2022070117025856157" <?php echo $guest && $guest['modelcode'.$i] == 'MP2022070117025856157' ? 'selected' : ''; ?>>标准票</option>
                            <option value="MP2022070419504838714" <?php echo $guest && $guest['modelcode'.$i] == 'MP2022070419504838714' ? 'selected' : ''; ?>>老人票</option>
                            <option value="MP2022070419411024189" <?php echo $guest && $guest['modelcode'.$i] == 'MP2022070419411024189' ? 'selected' : ''; ?>>学生票</option>
                            <option value="MP2022070117104622099" <?php echo $guest && $guest['modelcode'.$i] == 'MP2022070117104622099' ? 'selected' : ''; ?>>未成年</option>
                        </select>
                    </div>
                </div>
                <?php endfor; ?>
                
                <fieldset class="layui-elem-field layui-field-title">
                    <legend>抢票信息（请认真填写）</legend>
                </fieldset>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">客人组名</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <input type="text" name="group_name" id="group_name" lay-verify="required" placeholder="自动生成" autocomplete="off" class="layui-input" value="<?php echo $guest ? htmlspecialchars($guest['group_name']) : ''; ?>">
                    </div>
                    <label class="layui-form-label">手机号</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <input type="text" name="phone" lay-verify="required|phone" maxlength="11" placeholder="请输入手机号" autocomplete="off" class="layui-input" value="<?php echo $guest ? htmlspecialchars($guest['phone']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">购票日期</label>
                    <div class="layui-input-inline" style="width: 100px;">
                        <input type="text" name="ticket_date" id="ticket_date" lay-verify="required" placeholder="选择日期" autocomplete="off" class="layui-input" value="<?php echo $guest ? htmlspecialchars($guest['ticket_date']) : ''; ?>">
                    </div>
                    <div class="layui-input-inline" style="width: 90px;">
                        <select name="ticket_time" lay-verify="required">
                            <option value="全天" <?php echo (!$guest || $guest['ticket_time'] == '全天') ? 'selected' : ''; ?>>全天</option>
                            <option value="上午" <?php echo $guest && $guest['ticket_time'] == '上午' ? 'selected' : ''; ?>>上午</option>
                            <option value="下午" <?php echo $guest && $guest['ticket_time'] == '下午' ? 'selected' : ''; ?>>下午</option>
                        </select>
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">优先级</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <select name="priority" lay-verify="required">
                            <option value="1" <?php echo (!$guest || $guest['priority'] == 1) ? 'selected' : ''; ?>>1星</option>
                            <option value="2" <?php echo $guest && $guest['priority'] == 2 ? 'selected' : ''; ?>>2星</option>
                            <option value="3" <?php echo $guest && $guest['priority'] == 3 ? 'selected' : ''; ?>>3星</option>
                            <option value="4" <?php echo $guest && $guest['priority'] == 4 ? 'selected' : ''; ?>>4星</option>
                            <option value="5" <?php echo $guest && $guest['priority'] == 5 ? 'selected' : ''; ?>>5星</option>
                        </select>
                    </div>
                    <label class="layui-form-label">抢票wxid</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <input type="text" name="order_wxid" readonly placeholder="系统自动生成（无需填写）" autocomplete="off" class="layui-input" value="<?php echo $guest ? htmlspecialchars($guest['order_wxid']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">备注信息</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <input type="text" name="remarks" placeholder="请输入备注" autocomplete="off" class="layui-input" value="<?php echo $guest ? htmlspecialchars($guest['remarks']) : ''; ?>">
                    </div>
                    <label class="layui-form-label">状态</label>
                    <div class="layui-input-inline" style="width: 150px;">
                        <select name="status" lay-verify="required">
                            <option value="-4" <?php echo $guest && $guest['status'] == -4 ? 'selected' : ''; ?>>已退票</option>
                            <option value="-1" <?php echo $guest && $guest['status'] == -1 ? 'selected' : ''; ?>>有错误</option>
                            <option value="0" <?php echo !$guest || $guest['status'] == 0 ? 'selected' : ''; ?>>排队中</option>
                            <option value="1" <?php echo $guest && $guest['status'] == 1 ? 'selected' : ''; ?>>抢票中</option>
                            <option value="2" <?php echo $guest && $guest['status'] == 2 ? 'selected' : ''; ?>>已抢到</option>
                            <option value="3" <?php echo $guest && $guest['status'] == 3 ? 'selected' : ''; ?>>已生码</option>
                            <option value="9" <?php echo $guest && $guest['status'] == 9 ? 'selected' : ''; ?>>已付款</option>
                        </select>
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <div class="layui-input-block">
                        <input type="checkbox" name="reset_queue" lay-skin="primary" title="重置排队">
                        <button class="layui-btn" lay-submit lay-filter="saveBtn" style="margin-left: 20px;">立即提交</button>
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
    ,laydate = layui.laydate
    ,$ = layui.$;
    
    laydate.render({
        elem: '#ticket_date'
    });
    
    var isEdit = <?php echo $is_edit ? 'true' : 'false'; ?>;
    
    function getAgeFromIdCard(idCard) {
        if (!idCard || idCard.length !== 18) {
            return null;
        }
        
        var birthYear = parseInt(idCard.substring(6, 10));
        var birthMonth = parseInt(idCard.substring(10, 12));
        var birthDay = parseInt(idCard.substring(12, 14));
        
        var today = new Date();
        var currentYear = today.getFullYear();
        var currentMonth = today.getMonth() + 1;
        var currentDay = today.getDate();
        
        var age = currentYear - birthYear;
        
        if (currentMonth < birthMonth || (currentMonth === birthMonth && currentDay < birthDay)) {
            age--;
        }
        
        return age;
    }
    
    function autoSelectModelcode(index) {
        var idType = $('select[name="id_type' + index + '"]').val();
        var idNum = $('input[name="id_num' + index + '"]').val().trim();
        
        if (idType !== '0') {
            return;
        }
        
        if (!idNum || idNum.length !== 18) {
            return;
        }
        
        var age = getAgeFromIdCard(idNum);
        
        if (age === null) {
            return;
        }
        
        var modelcodeSelect = $('select[name="modelcode' + index + '"]');
        
        if (age >= 60) {
            modelcodeSelect.val('MP2022070419504838714');
        } else if (age >= 18) {
            modelcodeSelect.val('MP2022070117025856157');
        } else {
            modelcodeSelect.val('MP2022070117104622099');
        }
        
        form.render('select');
    }
    
    for (var i = 1; i <= 5; i++) {
        (function(index) {
            $('input[name="id_num' + index + '"]').on('blur', function() {
                autoSelectModelcode(index);
            });
            
            $('select[name="id_type' + index + '"]').on('change', function() {
                if ($(this).val() !== '0') {
                    $('select[name="modelcode' + index + '"]').val('');
                    form.render('select');
                } else {
                    autoSelectModelcode(index);
                }
            });
        })(i);
    }
    
    function updateGroupName() {
        if (isEdit) return;
        
        var name1 = $('input[name="name1"]').val().trim();
        
        if (name1) {
            $('#group_name').val(name1);
        } else {
            $('#group_name').val('');
        }
    }
    
    $('input[name^="name"]').on('input', function() {
        updateGroupName();
    });
    
    form.on('submit(saveBtn)', function(data){
        var hasPeople = false;
        
        for (var i = 1; i <= 5; i++) {
            var name = data.field['name' + i];
            var idNum = data.field['id_num' + i];
            var modelcode = data.field['modelcode' + i];
            
            if (name || idNum) {
                hasPeople = true;
            }
            
            if ((name && !idNum) || (!name && idNum)) {
                layer.msg('第' + i + '人的姓名和证件号必须同时填写或同时留空', {icon: 2});
                return false;
            }
            
            if ((name && idNum) && !modelcode) {
                layer.msg('第' + i + '人填写了姓名和证件号，必须选择票型', {icon: 2});
                return false;
            }
        }
        
        if (!hasPeople) {
            layer.msg('客人信息至少需要填写1人', {icon: 2}, function(){
                $('input[name="name1"]').focus();
            });
            return false;
        }
        
        return true;
    });
    
    form.render();
});
</script>
</body>
</html>
