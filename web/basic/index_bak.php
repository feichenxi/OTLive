<?php 
require("../data/class.php");

// Check if user is logged in
if (!isset($_SESSION['admin_id']) || $_SESSION['admin_id'] <= 0) {
    print '<script>window.location="/login.php";</script>';
    exit;
}

// Get user growth data for the last 30 days
$userGrowthData = array();
$dates = array();
for ($i = 29; $i >= 0; $i--) {
    $date = date('Y-m-d', strtotime("-$i days"));
    $dates[] = $date;
    
    // Count users registered on this date
    $sql = "SELECT COUNT(*) as count FROM user WHERE DATE(time) = '$date'";
    $result = mysqli_query($conn, $sql);
    if ($result) {
        $row = mysqli_fetch_assoc($result);
        $userGrowthData[] = (int)$row['count'];
    } else {
        // Log error and use 0 as default
        error_log("Failed to execute query: " . mysqli_error($conn) . " for date: " . $date);
        $userGrowthData[] = 0;
    }
}

// Get total user count
$totalUsersSql = "SELECT COUNT(*) as total FROM user";
$totalUsersResult = mysqli_query($conn, $totalUsersSql);
if ($totalUsersResult) {
    $totalUsersRow = mysqli_fetch_assoc($totalUsersResult);
    $totalUsers = $totalUsersRow['total'];
} else {
    $totalUsers = 0;
}

// Get today's new users
$today = date('Y-m-d');
$todaySql = "SELECT COUNT(*) as today FROM user WHERE DATE(time) = '$today'";
$todayResult = mysqli_query($conn, $todaySql);
if ($todayResult) {
    $todayRow = mysqli_fetch_assoc($todayResult);
    $todayUsers = $todayRow['today'];
} else {
    $todayUsers = 0;
}

// 获取待办事项数据
// 待建分身数量
$pendingRobotsSql = "SELECT COUNT(*) as count FROM user WHERE host > 0 AND status = 0";
$pendingRobotsResult = mysqli_query($conn, $pendingRobotsSql);
$pendingRobots = 0;
if ($pendingRobotsResult) {
    $pendingRobotsRow = mysqli_fetch_assoc($pendingRobotsResult);
    $pendingRobots = $pendingRobotsRow['count'];
}

// 违规分身数量
$violationRobotsSql = "SELECT COUNT(*) as count FROM user WHERE host > 0 AND status < 0";
$violationRobotsResult = mysqli_query($conn, $violationRobotsSql);
$violationRobots = 0;
if ($violationRobotsResult) {
    $violationRobotsRow = mysqli_fetch_assoc($violationRobotsResult);
    $violationRobots = $violationRobotsRow['count'];
}

// 总分身数量
$totalRobotsSql = "SELECT COUNT(*) as count FROM user WHERE host > 0";
$totalRobotsResult = mysqli_query($conn, $totalRobotsSql);
$totalRobots = 0;
if ($totalRobotsResult) {
    $totalRobotsRow = mysqli_fetch_assoc($totalRobotsResult);
    $totalRobots = $totalRobotsRow['count'];
}

// 启用中的分身数量
$activeRobotsSql = "SELECT COUNT(*) as count FROM user WHERE host > 0 AND status = 1";
$activeRobotsResult = mysqli_query($conn, $activeRobotsSql);
$activeRobots = 0;
if ($activeRobotsResult) {
    $activeRobotsRow = mysqli_fetch_assoc($activeRobotsResult);
    $activeRobots = $activeRobotsRow['count'];
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
      <div class="layui-col-md8">
        <div class="layui-row layui-col-space15">
          <div class="layui-col-md6">
            <div class="layui-card">
              <div class="layui-card-header">快捷方式</div>
              <div class="layui-card-body">
                
                <div class="layui-carousel layadmin-carousel layadmin-shortcut">
                  <div carousel-item>
                    <ul class="layui-row layui-col-space10">
                      <li class="layui-col-xs3">
                        <a href="../robot/index.php">
                          <i class="layui-icon layui-icon-friends"></i>
                          <cite>分身列表</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="../robot/oneself_list.php">
                          <i class="layui-icon layui-icon-username"></i>
                          <cite>备选人物</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="user_list.php">
                          <i class="layui-icon layui-icon-user"></i>
                          <cite>用户管理</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="../robot/cat_list.php">
                          <i class="layui-icon layui-icon-template-1"></i>
                          <cite>分类管理</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="ad_list.php">
                          <i class="layui-icon layui-icon-carousel"></i>
                          <cite>广告管理</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="chat_list.php">
                          <i class="layui-icon layui-icon-chat"></i>
                          <cite>对话列表</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="financial_list.php">
                          <i class="layui-icon layui-icon-dollar"></i>
                          <cite>财务记录</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="password.php">
                          <i class="layui-icon layui-icon-password"></i>
                          <cite>修改密码</cite>
                        </a>
                      </li>
                      <li class="layui-col-xs3">
                        <a href="../login.php?t=logout">
                          <i class="layui-icon layui-icon-logout"></i>
                          <cite>退出登录</cite>
                        </a>
                      </li>
                    </ul>
                  </div>
                </div>
                
              </div>
            </div>
          </div>
          <div class="layui-col-md6">
            <div class="layui-card">
              <div class="layui-card-header">待办事项</div>
              <div class="layui-card-body">

                <div class="layui-carousel layadmin-carousel layadmin-backlog">
                  <div carousel-item>
                    <ul class="layui-row layui-col-space10">
                      <li class="layui-col-xs6">
                        <a href="../robot/list.php" class="layadmin-backlog-body">
                          <h3>待建分身</h3>
                          <p><cite style="<?php echo $pendingRobots > 0 ? 'color: #FFB800;' : ''; ?>"><?php echo $pendingRobots; ?></cite></p>
                        </a>
                      </li>
                      <li class="layui-col-xs6">
                        <a href="../robot/list.php" class="layadmin-backlog-body">
                          <h3>违规分身</h3>
                          <p><cite style="<?php echo $violationRobots > 0 ? 'color: #FF5722;' : ''; ?>"><?php echo $violationRobots; ?></cite></p>
                        </a>
                      </li>
                      <li class="layui-col-xs6">
                        <a href="../robot/list.php" class="layadmin-backlog-body">
                          <h3>总分身数</h3>
                          <p><cite><?php echo $totalRobots; ?></cite></p>
                        </a>
                      </li>
                      <li class="layui-col-xs6">
                        <a href="../robot/list.php" class="layadmin-backlog-body">
                          <h3>启用中</h3>
                          <p><cite style="color: #28a745;"><?php echo $activeRobots; ?></cite></p>
                        </a>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="layui-col-md12">
            <div class="layui-card">
              <div class="layui-card-header">数据概览</div>
              <div class="layui-card-body">
                
                <div class="layui-carousel layadmin-carousel layadmin-backlog">
                  <div carousel-item>
                    <ul class="layui-row layui-col-space10">
                      <li class="layui-col-xs6">
                        <a href="user_list.php" class="layadmin-backlog-body">
                          <h3>总用户数</h3>
                          <p><cite><?php echo $totalUsers; ?></cite></p>
                        </a>
                      </li>
                      <li class="layui-col-xs6">
                        <a href="user_list.php" class="layadmin-backlog-body">
                          <h3>今日新增</h3>
                          <p><cite style="color: #1890ff;"><?php echo $todayUsers; ?></cite></p>
                        </a>
                      </li>
                    </ul>
                  </div>
                </div>
                
              </div>
            </div>
          </div>
          <div class="layui-col-md12">
            <div class="layui-card">
              <div class="layui-card-header">用户成长趋势</div>
              <div class="layui-card-body">
                
                <div id="user-growth-chart" style="width: 100%; height: 400px;"></div>
                
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="layui-col-md4">
        <div class="layui-card">
          <div class="layui-card-header">版本信息</div>
          <div class="layui-card-body layui-text">
            <table class="layui-table">
              <colgroup>
                <col width="100">
                <col>
              </colgroup>
              <tbody>
                <tr>
                  <td>当前版本</td>
                  <td>
                    v1.0.0
                    <a href="javascript:;" style="padding-left: 15px;">更新日志</a>
                  </td>
                </tr>
                <tr>
                  <td>基于框架</td>
                  <td>
                    layui-v2.5.6
                 </td>
                </tr>
                <tr>
                  <td>主要特色</td>
                  <td>简洁 / 高效 / 实用</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        
        <div class="layui-card">
          <div class="layui-card-header">效果报告</div>
          <div class="layui-card-body layadmin-takerates">
            <div class="layui-progress" lay-showPercent="yes">
              <h3>用户增长率（日同比 15% <span class="layui-edge layui-edge-top" lay-tips="增长" lay-offset="-15"></span>）</h3>
              <div class="layui-progress-bar" lay-percent="75%"></div>
            </div>
            <div class="layui-progress" lay-showPercent="yes">
              <h3>活跃度（日同比 8% <span class="layui-edge layui-edge-top" lay-tips="增长" lay-offset="-15"></span>）</h3>
              <div class="layui-progress-bar" lay-percent="60%"></div>
            </div>
          </div>
        </div>
        
        <div class="layui-card">
          <div class="layui-card-header">实时监控</div>
          <div class="layui-card-body layadmin-takerates">
            <div class="layui-progress" lay-showPercent="yes">
              <h3>CPU使用率</h3>
              <div class="layui-progress-bar" lay-percent="45%"></div>
            </div>
            <div class="layui-progress" lay-showPercent="yes">
              <h3>内存占用率</h3>
              <div class="layui-progress-bar layui-bg-red" lay-percent="70%"></div>
            </div>
          </div>
        </div>

        <div class="layui-card">
          <div class="layui-card-header">
            系统信息
            <i class="layui-icon layui-icon-tips" lay-tips="系统相关信息" lay-offset="5"></i>
          </div>
          <div class="layui-card-body layui-text layadmin-text">
            <p>系统运行稳定，用户增长趋势良好。</p>
            <p>建议持续关注用户活跃度和留存率。</p>
            <p>定期清理无效数据，保持系统高效运行。</p>
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
  
  // Debug data
  console.log('Dates:', dates);
  console.log('User Data:', userData);
  console.log('Dates length:', dates.length);
  console.log('User Data length:', userData.length);
  
  // Initialize chart when DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Ready, ECharts:', typeof echarts);
    
    if (typeof echarts !== 'undefined') {
      var chartElement = document.getElementById('user-growth-chart');
      console.log('Chart Element:', chartElement);
      
      if (chartElement) {
        var chart = echarts.init(chartElement);
        
        var option = {
          title: {
            text: '最近30天用户增长趋势'
          },
          tooltip: {
            trigger: 'axis'
          },
          xAxis: {
            type: 'category',
            data: dates
          },
          yAxis: {
            type: 'value'
          },
          series: [{
            data: userData,
            type: 'line',
            smooth: true
          }]
        };
        
        console.log('Setting chart option:', option);
        chart.setOption(option);
      }
    }
  });
  </script>
</body>
</html>