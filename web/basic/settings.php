<?php
require("../data/class.php");

// 处理AJAX保存请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    header('Content-Type: application/json;charset=utf-8');
    
    $action = $_POST['action'];
    
    if ($action === 'saveAll') {
        $settings = isset($_POST['settings']) ? $_POST['settings'] : [];
        
        if (empty($settings) || !is_array($settings)) {
            echo json_encode(['code' => 1, 'msg' => '参数错误']);
            exit;
        }
        
        $success = 0;
        $fail = 0;
        
        foreach ($settings as $key => $value) {
            $key_escaped = mysqli_real_escape_string($conn, $key);
            $value_escaped = mysqli_real_escape_string($conn, $value);
            
            $sql = "UPDATE settings SET `value` = '{$value_escaped}' WHERE `key` = '{$key_escaped}'";
            if (mysqli_query($conn, $sql)) {
                $success++;
            } else {
                $fail++;
            }
        }
        
        echo json_encode([
            'code' => 0, 
            'msg' => "保存成功{$success}项" . ($fail > 0 ? "，失败{$fail}项" : '')
        ]);
        exit;
    }
    
    echo json_encode(['code' => 1, 'msg' => '未知操作']);
    exit;
}

// 获取分组参数
$group = isset($_GET['group']) ? trim($_GET['group']) : 'basic';

// 分组名称映射
$groupNames = [
    'basic' => '基础设置',
    'order' => '订单设置',
    'pay' => '支付设置',
    'wx' => '微信支付',
    'alipay' => '支付宝支付',
    'sms' => '短信配置',
    'other' => '其他设置'
];

// 验证分组有效性
if (!isset($groupNames[$group])) {
    $group = 'basic';
}

// 获取指定分组的设置（排除已废弃的距离相关字段）
$excludeKeys = ['order_distance_fee', 'order_base_distance'];
$excludeStr = "'" . implode("','", $excludeKeys) . "'";
$sql = "SELECT * FROM settings WHERE `group` = '{$group}' AND `key` NOT IN ({$excludeStr}) ORDER BY sort, id";
$result = mysqli_query($conn, $sql);

$items = [];
while ($row = mysqli_fetch_assoc($result)) {
    $items[] = $row;
}

$pageTitle = $groupNames[$group];
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
    <title><?php echo $pageTitle; ?></title>
</head>
<body>

<div class="layui-fluid">
    <div class="layui-row layui-col-space15">
        <div class="layui-col-md12">
            <div class="layui-card">
                <div class="layui-card-header"><?php echo $pageTitle; ?></div>
                <div class="layui-card-body" pad15>
                    <form class="layui-form" id="settingsForm">
                        <?php foreach ($items as $item): ?>
                        <div class="layui-form-item">
                            <label class="layui-form-label" style="width: 200px;"><?php echo htmlspecialchars($item['title']); ?></label>
                            <div class="layui-input-inline" style="width: 230px;">
                                <?php if ($item['type'] === 'number'): ?>
                                <input type="number" name="settings[<?php echo htmlspecialchars($item['key']); ?>]" 
                                       value="<?php echo htmlspecialchars($item['value']); ?>" 
                                       class="layui-input">
                                <?php elseif ($item['type'] === 'json'): ?>
                                <textarea name="settings[<?php echo htmlspecialchars($item['key']); ?>]" 
                                          class="layui-textarea" rows="3"><?php echo htmlspecialchars($item['value']); ?></textarea>
                                <?php else: ?>
                                <input type="text" name="settings[<?php echo htmlspecialchars($item['key']); ?>]" 
                                       value="<?php echo htmlspecialchars($item['value']); ?>" 
                                       class="layui-input">
                                <?php endif; ?>
                            </div>
                            <?php if ($item['description']): ?>
                            <div class="layui-form-mid layui-word-aux"><?php echo htmlspecialchars($item['description']); ?></div>
                            <?php endif; ?>
                        </div>
                        <?php endforeach; ?>
                        
                        <div class="layui-form-item">
                            <div class="layui-input-block">
                                <button type="button" class="layui-btn" id="saveBtn">保存设置</button>
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
layui.use(['form', 'layer'], function(){
    var $ = layui.$;
    var form = layui.form;
    var layer = layui.layer;
    
    // 保存设置
    $('#saveBtn').on('click', function(){
        var btn = $(this);
        var formData = $('#settingsForm').serialize();
        
        btn.prop('disabled', true).text('保存中...');
        
        $.ajax({
            url: 'settings.php?group=<?php echo $group; ?>',
            type: 'POST',
            data: 'action=saveAll&' + formData,
            dataType: 'json',
            success: function(res){
                if(res.code === 0){
                    layer.msg(res.msg, {icon: 1});
                } else {
                    layer.msg(res.msg || '保存失败', {icon: 2});
                }
            },
            error: function(){
                layer.msg('请求失败', {icon: 2});
            },
            complete: function(){
                btn.prop('disabled', false).text('保存设置');
            }
        });
    });
});
</script>

</body>
</html>
