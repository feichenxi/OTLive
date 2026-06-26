<?php 
require("../data/class.php");

// Check if user is logged in
if (!isset($_SESSION['admin_id']) || $_SESSION['admin_id'] <= 0) {
    print '<script>window.location="/login.php";</script>';
    exit;
}

// 获取统计数据
$today = date('Y-m-d');
$month_start = date('Y-m-01');

// 今日订单数
$sql = "SELECT COUNT(*) as count FROM orders_pickup WHERE DATE(create_time) = '{$today}'";
$result = mysqli_query($_ENV['conn'], $sql);
$today_orders = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

$sql = "SELECT SUM(pay_amount) as amount FROM orders_pickup WHERE DATE(create_time) = '{$today}' AND status IN (1,2,3,4)";
$result = mysqli_query($_ENV['conn'], $sql);
$today_amount = ($result && mysqli_num_rows($result) > 0) ? (mysqli_fetch_assoc($result)['amount'] ?: 0) : 0;

$sql = "SELECT COUNT(*) as count FROM orders_pickup WHERE status = 1";
$result = mysqli_query($_ENV['conn'], $sql);
$pending_orders = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

$sql = "SELECT COUNT(*) as count FROM users";
$result = mysqli_query($_ENV['conn'], $sql);
$total_users = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

$sql = "SELECT COUNT(*) as count FROM runner_cert WHERE status = 0";
$result = mysqli_query($_ENV['conn'], $sql);
$pending_runners = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

$sql = "SELECT COUNT(*) as count FROM withdrawals WHERE status = 0";
$result = mysqli_query($_ENV['conn'], $sql);
$pending_withdrawals = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

$sql = "SELECT COUNT(*) as count FROM orders_pickup";
$result = mysqli_query($_ENV['conn'], $sql);
$total_orders = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

$sql = "SELECT SUM(pay_amount) as amount FROM orders_pickup WHERE create_time >= '{$month_start}' AND status IN (1,2,3,4)";
$result = mysqli_query($_ENV['conn'], $sql);
$month_amount = ($result && mysqli_num_rows($result) > 0) ? (mysqli_fetch_assoc($result)['amount'] ?: 0) : 0;

$sql = "SELECT COUNT(*) as count FROM orders_pickup WHERE status = 3";
$result = mysqli_query($_ENV['conn'], $sql);
$delivering_orders = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

// 跑腿员数
$sql = "SELECT COUNT(*) as count FROM users WHERE is_runner = 1";
$result = mysqli_query($_ENV['conn'], $sql);
$runner_count = ($result && mysqli_num_rows($result) > 0) ? mysqli_fetch_assoc($result)['count'] : 0;

// 获取用户增长数据（最近30天）
$userGrowthData = array();
$dates = array();
for ($i = 29; $i >= 0; $i--) {
    $date = date('Y-m-d', strtotime("-$i days"));
    $dates[] = $date;
    
    $sql = "SELECT COUNT(*) as count FROM users WHERE DATE(create_time) = '$date'";
    $result = mysqli_query($_ENV['conn'], $sql);
    if ($result) {
        $row = mysqli_fetch_assoc($result);
        $userGrowthData[] = (int)$row['count'];
    } else {
        $userGrowthData[] = 0;
    }
}

// 最近订单
$sql = "SELECT o.*, u.nickname, u.phone as user_phone 
        FROM orders_pickup o 
        LEFT JOIN users u ON o.user_id = u.id 
        ORDER BY o.create_time DESC LIMIT 10";
$result = mysqli_query($_ENV['conn'], $sql);
$recent_orders = array();
if ($result) {
    while ($row = mysqli_fetch_assoc($result)) {
        $recent_orders[] = $row;
    }
}

// 最近用户
$sql = "SELECT * FROM users ORDER BY create_time DESC LIMIT 10";
$result = mysqli_query($_ENV['conn'], $sql);
$recent_users = array();
if ($result) {
    while ($row = mysqli_fetch_assoc($result)) {
        $recent_users[] = $row;
    }
}

$order_status = array(
    0 => array('text' => '待支付', 'class' => 'layui-bg-orange'),
    1 => array('text' => '待接单', 'class' => 'layui-bg-blue'),
    2 => array('text' => '已接单', 'class' => 'layui-bg-cyan'),
    3 => array('text' => '配送中', 'class' => 'layui-bg-green'),
    4 => array('text' => '已完成', 'class' => 'layui-bg-gray'),
    5 => array('text' => '已取消', 'class' => 'layui-bg-gray'),
);

$user_status = array(
    0 => array('text' => '禁用', 'class' => 'layui-bg-gray'),
    1 => array('text' => '正常', 'class' => 'layui-bg-green'),
);
?>
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>控制台</title>
  <meta name="renderer" content="webkit">
  <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
  <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
  <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>
  
  <div class="layui-fluid">
    <div class="layui-row layui-col-space15">
      <!-- 统计卡片 -->
      <div class="layui-col-md3">
        <div class="layui-card">
          <div class="layui-card-header">
            今日订单
            <span class="layui-badge layui-bg-blue layuiadmin-badge">今日</span>
          </div>
          <div class="layui-card-body layuiadmin-card-list">
            <p class="layuiadmin-big-font"><?php print $today_orders; ?></p>
            <p>总订单数 <span class="layuiadmin-span-color"><?php print $total_orders; ?> <i class="layui-inline layui-icon layui-icon-flag"></i></span></p>
          </div>
        </div>
      </div>
      
      <div class="layui-col-md3">
        <div class="layui-card">
          <div class="layui-card-header">
            今日收入
            <span class="layui-badge layui-bg-green layuiadmin-badge">今日</span>
          </div>
          <div class="layui-card-body layuiadmin-card-list">
            <p class="layuiadmin-big-font">¥<?php print number_format($today_amount, 2); ?></p>
            <p>本月收入 <span class="layuiadmin-span-color">¥<?php print number_format($month_amount, 2); ?> <i class="layui-inline layui-icon layui-icon-rmb"></i></span></p>
          </div>
        </div>
      </div>
      
      <div class="layui-col-md3">
        <div class="layui-card">
          <div class="layui-card-header">
            待处理订单
            <span class="layui-badge layui-bg-orange layuiadmin-badge">待处理</span>
          </div>
          <div class="layui-card-body layuiadmin-card-list">
            <p class="layuiadmin-big-font"><?php print $pending_orders; ?></p>
            <p>配送中 <span class="layuiadmin-span-color"><?php print $delivering_orders; ?> <i class="layui-inline layui-icon layui-icon-ok-circle"></i></span></p>
          </div>
        </div>
      </div>
      
      <div class="layui-col-md3">
        <div class="layui-card">
          <div class="layui-card-header">
            总用户数
            <span class="layui-badge layui-bg-cyan layuiadmin-badge">全部</span>
          </div>
          <div class="layui-card-body layuiadmin-card-list">
            <p class="layuiadmin-big-font"><?php print $total_users; ?></p>
            <p>跑腿员 <span class="layuiadmin-span-color"><?php print $runner_count; ?> <i class="layui-inline layui-icon layui-icon-user"></i></span></p>
          </div>
        </div>
      </div>

      <!-- 快捷入口 -->
      <div class="layui-col-md12">
        <div class="layui-card">
          <div class="layui-card-header">快捷入口</div>
          <div class="layui-card-body">
            <div class="layui-row layui-col-space10">
              <div class="layui-col-xs2">
                <a href="javascript:;" onclick="parent.layui.index.openTabsPage('../ex/order_list.php?status=1', '待处理订单')" class="layadmin-backlog-body">
                  <h3>待接单</h3>
                  <p><cite><?php print $pending_orders; ?></cite></p>
                </a>
              </div>
              <div class="layui-col-xs2">
                <a href="javascript:;" onclick="parent.layui.index.openTabsPage('../ex/runner_list.php?status=0', '待审核跑腿员')" class="layadmin-backlog-body">
                  <h3>待审核跑腿员</h3>
                  <p><cite style="color: #FF5722;"><?php print $pending_runners; ?></cite></p>
                </a>
              </div>
              <div class="layui-col-xs2">
                <a href="javascript:;" onclick="parent.layui.index.openTabsPage('../ex/withdraw_list.php?status=0', '待处理提现')" class="layadmin-backlog-body">
                  <h3>待处理提现</h3>
                  <p><cite style="color: #FF5722;"><?php print $pending_withdrawals; ?></cite></p>
                </a>
              </div>
              <div class="layui-col-xs2">
                <a href="javascript:;" onclick="parent.layui.index.openTabsPage('../ex/user_list.php', '用户管理')" class="layadmin-backlog-body">
                  <h3>用户管理</h3>
                  <p><cite><?php print $total_users; ?></cite></p>
                </a>
              </div>
              <div class="layui-col-xs2">
                <a href="javascript:;" onclick="parent.layui.index.openTabsPage('../ex/banner_list.php', '轮播图管理')" class="layadmin-backlog-body">
                  <h3>轮播图管理</h3>
                  <p><cite>配置</cite></p>
                </a>
              </div>
              <div class="layui-col-xs2">
                <a href="javascript:;" onclick="parent.layui.index.openTabsPage('../ex/notice_list.php', '公告管理')" class="layadmin-backlog-body">
                  <h3>公告管理</h3>
                  <p><cite>发布</cite></p>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 最近订单 -->
      <div class="layui-col-md8">
        <div class="layui-card">
          <div class="layui-card-header">最近快递代取订单</div>
          <div class="layui-card-body">
            <table class="layui-table">
              <thead>
                <tr>
                  <th>订单号</th>
                  <th>标题</th>
                  <th>用户信息</th>
                  <th>金额</th>
                  <th>状态</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                <?php foreach ($recent_orders as $order): ?>
                <tr>
                  <td><?php print $order['order_no']; ?></td>
                  <td><?php print $order['title']; ?></td>
                  <td><?php print $order['nickname'] ?: $order['user_phone']; ?></td>
                  <td>¥<?php print number_format($order['pay_amount'], 2); ?></td>
                  <td><span class="layui-badge <?php print $order_status[$order['status']]['class'] ?? 'layui-bg-gray'; ?>"><?php print $order_status[$order['status']]['text'] ?? '未知'; ?></span></td>
                  <td><?php print date('m-d H:i', strtotime($order['create_time'])); ?></td>
                </tr>
                <?php endforeach; ?>
                <?php if (empty($recent_orders)): ?>
                <tr>
                  <td colspan="6" style="text-align: center;">暂无订单数据</td>
                </tr>
                <?php endif; ?>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 最近用户 -->
      <div class="layui-col-md4">
        <div class="layui-card">
          <div class="layui-card-header">最近注册用户</div>
          <div class="layui-card-body">
            <table class="layui-table">
              <thead>
                <tr>
                  <th>用户</th>
                  <th>状态</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                <?php foreach ($recent_users as $user): ?>
                <tr>
                  <td>
                    <img src="<?php print $user['avatar'] ?: '/uploads/avatar/default.png'; ?>" class="layui-nav-img" style="width: 30px; height: 30px; border-radius: 50%;" onerror="this.src='/uploads/avatar/default.png'">
                    <?php print $user['nickname'] ?: '用户' . $user['id']; ?>
                  </td>
                  <td><span class="layui-badge <?php print $user_status[$user['status']]['class'] ?? 'layui-bg-gray'; ?>"><?php print $user_status[$user['status']]['text'] ?? '未知'; ?></span></td>
                  <td><?php print date('m-d H:i', strtotime($user['create_time'])); ?></td>
                </tr>
                <?php endforeach; ?>
                <?php if (empty($recent_users)): ?>
                <tr>
                  <td colspan="3" style="text-align: center;">暂无用户数据</td>
                </tr>
                <?php endif; ?>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 用户增长趋势 -->
      <div class="layui-col-md12">
        <div class="layui-card">
          <div class="layui-card-header">用户增长趋势（最近30天）</div>
          <div class="layui-card-body">
            <div id="user-growth-chart" style="width: 100%; height: 300px;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script src="../public/lib/extend/echarts.js"></script>
  <script src="../public/layui/layui.js"></script>  
  <script>
  // 初始化图表
  var dates = <?php echo json_encode($dates); ?>;
  var userData = <?php echo json_encode($userGrowthData); ?>;
  
  layui.use(['layer'], function(){
    var layer = layui.layer;
    
    // 初始化图表
    if (typeof echarts !== 'undefined') {
      var chartElement = document.getElementById('user-growth-chart');
      if (chartElement) {
        var chart = echarts.init(chartElement);
        
        var option = {
          tooltip: {
            trigger: 'axis'
          },
          xAxis: {
            type: 'category',
            data: dates,
            axisLabel: {
              rotate: 45
            }
          },
          yAxis: {
            type: 'value'
          },
          series: [{
            data: userData,
            type: 'line',
            smooth: true,
            areaStyle: {
              color: {
                type: 'linear',
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(0, 150, 136, 0.3)' },
                  { offset: 1, color: 'rgba(0, 150, 136, 0.05)' }
                ]
              }
            },
            lineStyle: {
              color: '#009688'
            },
            itemStyle: {
              color: '#009688'
            }
          }]
        };
        
        chart.setOption(option);
        
        // 响应式
        window.addEventListener('resize', function() {
          chart.resize();
        });
      }
    }
  });
  </script>
</body>
</html>
