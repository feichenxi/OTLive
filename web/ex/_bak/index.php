<?php 
require("../data/class.php");

// Check if user is logged in
if (!isset($_SESSION['admin_id']) || $_SESSION['admin_id'] <= 0) {
    print '<script>window.location="/login.php";</script>';
    exit;
}

// 获取day表中id=1的记录
$daySql = "SELECT * FROM day WHERE id = 1";
$dayResult = mysqli_query($conn, $daySql);
$dayData = array();
if ($dayResult) {
    $dayData = mysqli_fetch_assoc($dayResult);
}

// 设置默认值
if (!isset($dayData['submit_ratio'])) {
    $dayData['submit_ratio'] = '1';
}
if (!isset($dayData['submit_last']) || empty($dayData['submit_last'])) {
    $dayData['submit_last'] = '08:40:00';
}

// 处理表单提交
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_day'])) {
    $checkDate = mysqli_real_escape_string($conn, $_POST['check_date']);
    $checkInterval = mysqli_real_escape_string($conn, $_POST['check_interval']);
    $submitRatio = mysqli_real_escape_string($conn, $_POST['submit_ratio']);
    $submitLast = mysqli_real_escape_string($conn, $_POST['submit_last']);
    $currentDate = date('Y-m-d H:i:s');
    
    $updateSql = "UPDATE day SET check_date = '$checkDate', check_interval = '$checkInterval', submit_ratio = '$submitRatio', submit_last = '$submitLast', updated_at = '$currentDate' WHERE id = 1";
    if (mysqli_query($conn, $updateSql)) {
        $dayData['check_date'] = $checkDate;
        $dayData['check_interval'] = $checkInterval;
        $dayData['submit_ratio'] = $submitRatio;
        $dayData['submit_last'] = $submitLast;
        $dayData['updated_at'] = $currentDate;
        $successMsg = "保存成功!";
    } else {
        $errorMsg = "保存失败: " . mysqli_error($conn);
    }
}

// 检查更新日期是否为今天
$today = date('Y-m-d');
$needWarning = false;
if (isset($dayData['updated_at'])) {
    $updateDate = substr($dayData['updated_at'], 0, 10);
    $needWarning = ($updateDate !== $today);
}

// 计算7天后的日期
$sevenDaysLater = date('Y-m-d', strtotime('+7 days'));

// 检查查票日期是否等于最晚可约日期
$dateWarning = false;
if (isset($dayData['check_date']) && !empty($dayData['check_date'])) {
    $dateWarning = ($dayData['check_date'] !== $sevenDaysLater);
}


?>
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>数据统计</title>
  <meta name="renderer" content="webkit">
  <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
  <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
  <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>
  
  <div class="layui-fluid">
    <div class="layui-row layui-col-space15">
      <div class="layui-col-md4">
        <div class="layui-card">
          <div class="layui-card-header">查票设置</div>
          <div class="layui-card-body">
            <?php if (isset($successMsg)): ?>
            <div class="layui-alert layui-alert-success" style="margin-bottom: 15px; padding: 10px; background: #5FB878; color: #fff;">
              <?php echo $successMsg; ?>
            </div>
            <?php endif; ?>
            <?php if (isset($errorMsg)): ?>
            <div class="layui-alert layui-alert-error" style="margin-bottom: 15px; padding: 10px; background: #FF5722; color: #fff;">
              <?php echo $errorMsg; ?>
            </div>
            <?php endif; ?>
            <form class="layui-form" method="POST">
              <?php if ($needWarning): ?>
              <div class="layui-form-item">
                <div class="layui-input-block" style="width: 100%; margin-left: 0;">
                  <div class="layui-alert layui-alert-warning" style="padding: 15px; background: #FF5722; color: #fff; border-radius: 4px; font-size: 16px; font-weight: bold;">
                    <i class="layui-icon layui-icon-tips" style="margin-right: 8px;"></i>请先设置今天的查票日期，所有客户机均以此日期为准！
                  </div>
                </div>
              </div>
              <?php endif; ?>
              <div class="layui-form-item">
                <label class="layui-form-label">查票日期</label>
                <div class="layui-input-inline" style="width: 200px;">
                  <input type="text" name="check_date" id="check_date" value="<?php echo isset($dayData['check_date']) ? htmlspecialchars($dayData['check_date']) : ''; ?>" placeholder="请选择查票日期" autocomplete="off" class="layui-input">
                  <?php if ($dateWarning): ?>
                  <div class="layui-alert layui-alert-warning" style="margin-top: 5px; padding: 8px 12px; background: #FFB800; color: #fff; border-radius: 2px; font-size: 13px; text-align: left;">
                   查票与最晚可约不同，确认？
                  </div>
                  <?php endif; ?>
                </div>
                <div class="layui-form-mid layui-word-aux">最晚可约【<?php echo $sevenDaysLater; ?>】</div>
              </div>
              <div class="layui-form-item">
                <label class="layui-form-label">查票间隔</label>
                <div class="layui-input-block">
                  <div class="layui-input-inline" style="width: 200px;">
                    <input type="text" name="check_interval" value="<?php echo isset($dayData['check_interval']) ? htmlspecialchars($dayData['check_interval']) : ''; ?>" placeholder="请输入查票间隔" autocomplete="off" class="layui-input">
                  </div>
                  <div class="layui-form-mid layui-word-aux">毫秒</div>
                </div>
              </div>
              <div class="layui-form-item">
                <label class="layui-form-label">账号配比</label>
                <div class="layui-input-block">
                  <div style="display: flex; align-items: center;">
                    <span style="margin-right: 8px;">1：</span>
                    <div class="layui-input-inline" style="width: 60px;">
                      <input type="text" name="submit_ratio" value="<?php echo isset($dayData['submit_ratio']) ? htmlspecialchars($dayData['submit_ratio']) : '1'; ?>" placeholder="请输入" autocomplete="off" class="layui-input">
                    </div>
                     <div class="layui-form-mid layui-word-aux">如1组客人配6个账号则为1：6</div>
                  </div>
                </div>
              </div>
              <div class="layui-form-item">
                <label class="layui-form-label">冲刺时间</label>
                <div class="layui-input-block">
                  <div class="layui-input-inline" style="width: 200px;">
                    <input type="text" name="submit_last" id="submit_last" value="<?php echo isset($dayData['submit_last']) && !empty($dayData['submit_last']) ? htmlspecialchars($dayData['submit_last']) : '08:40:00'; ?>" placeholder="请选择最后批次时间" autocomplete="off" class="layui-input">
                  </div>
                  <div class="layui-form-mid layui-word-aux">24小时制，默认8:40</div>
                </div>
              </div>
              <div class="layui-form-item">
                <label class="layui-form-label">更新时间</label>
                <div class="layui-input-block" style="width: 200px;">
                  <input type="text" value="<?php echo isset($dayData['updated_at']) ? htmlspecialchars($dayData['updated_at']) : ''; ?>" readonly class="layui-input layui-disabled">
                </div>
              </div>
              <div class="layui-form-item">
                <div class="layui-input-block">
                  <button type="submit" name="update_day" class="layui-btn" lay-submit lay-filter="formDemo">保存</button>
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
  layui.use(['form', 'laydate'], function(){
    var form = layui.form;
    var laydate = layui.laydate;

    // 渲染表单
    form.render();

    // 日期选择器
    laydate.render({
      elem: '#check_date',
      type: 'date',
      format: 'yyyy-MM-dd',
      trigger: 'click'
    });

    // 时间选择器
    laydate.render({
      elem: '#submit_last',
      type: 'time',
      format: 'HH:mm:ss',
      trigger: 'click'
    });
  });
  </script>
</body>
</html>