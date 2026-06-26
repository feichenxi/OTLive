<?php require("data/class.php");?>
<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
	<title><?php print $setting['app_name'];?> - 后台管理系统</title>
	<meta name="renderer" content="webkit">
	<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
	<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
	<link rel="stylesheet" href="public/layui/css/layui.css" media="all">
	<link rel="stylesheet" href="public/style/admin.css" media="all">
	<?php $t=$_GET['t'] ?? '';?>
</head>
<body class="layui-layout-body">
  
  <div id="LAY_app">
    <div class="layui-layout layui-layout-admin">
      <div class="layui-header">
        <!-- 头部区域 -->
        <ul class="layui-nav layui-layout-left">
        
          <li class="layui-nav-item layadmin-flexible" lay-unselect>
            <a href="javascript:;" layadmin-event="flexible" title="侧边伸缩">
              <i class="layui-icon layui-icon-shrink-right" id="LAY_app_flexible"></i>
            </a>
          </li>

          <li class="layui-nav-item" lay-unselect>
            <a href="javascript:;" layadmin-event="refresh" title="刷新">
              <i class="layui-icon layui-icon-refresh-3"></i>
            </a>
        
        </ul>
        <ul class="layui-nav layui-layout-right" lay-filter="layadmin-layout-right">
          
        
          <li class="layui-nav-item layui-hide-xs" lay-unselect>
            <a href="javascript:;" layadmin-event="theme">
              <i class="layui-icon layui-icon-theme"></i>
            </a>
          </li>
          <li class="layui-nav-item layui-hide-xs" lay-unselect>
            <a href="javascript:;" layadmin-event="note">
              <i class="layui-icon layui-icon-note"></i>
            </a>
          </li>
          <li class="layui-nav-item layui-hide-xs" lay-unselect>
            <a href="javascript:;" layadmin-event="fullscreen">
              <i class="layui-icon layui-icon-screen-full"></i>
            </a>
          </li>
          <li class="layui-nav-item" lay-unselect>
            <a href="javascript:;">
              <cite><?php print $_SESSION['username'];?></cite>
            </a>
            <dl class="layui-nav-child">
              <dd><a lay-href="basic/password.php">修改密码</a></dd>
              <hr>
              <dd style="text-align: center;"><a href="login.php?t=logout">退出</a></dd>
            </dl>
          </li>
          
          <li class="layui-nav-item layui-hide-xs" lay-unselect>
            <a href="javascript:msg('暂无展示信息');" ><i class="layui-icon layui-icon-more-vertical"></i></a>
          </li>
          <li class="layui-nav-item layui-show-xs-inline-block layui-hide-sm" lay-unselect>
            <a href="javascript:msg('暂无展示信息');"><i class="layui-icon layui-icon-more-vertical"></i></a>
          </li>
        </ul>
      </div>
        
        
      <!-- 侧边菜单 -->
    <div class="layui-side layui-side-menu"><div class="layui-side-scroll">
        <div class="layui-logo" style="cursor:pointer"><span id="logo_title_user"><?php print $setting['app_name'];?></span></div>
        <ul class="layui-nav layui-nav-tree" lay-shrink="all" id="LAY-system-side-menu" lay-filter="layadmin-system-side-menu">

            <!-- 首页 -->
            <li data-name="home" class="layui-nav-item layui-nav-itemed">
                <a href="javascript:;" lay-tips="首页" lay-direction="2"><i class="layui-icon layui-icon-home"></i><cite>首页</cite></a>
                <dl class="layui-nav-child">
                    <dd data-name="console" class="layui-this"><a lay-href="basic/index.php">控制台</a></dd>
                </dl>
            </li>

            <!-- 用户管理 -->
            <li data-name="user" class="layui-nav-item">
                <a href="javascript:;" lay-tips="用户管理" lay-direction="2"><i class="layui-icon layui-icon-username"></i><cite>用户管理</cite></a>
                <dl class="layui-nav-child">
                    <dd data-name="user_list"><a lay-href="ex/user_list.php">用户列表</a></dd>
                    <dd data-name="address_list"><a lay-href="ex/address_list.php">地址管理</a></dd>
                    <dd data-name="runner_list"><a lay-href="ex/runner_list.php">跑腿员管理</a></dd>
                </dl>
            </li>

            <!-- 订单管理 -->
            <li data-name="order" class="layui-nav-item">
                <a href="javascript:;" lay-tips="订单管理" lay-direction="2"><i class="layui-icon layui-icon-template-1"></i><cite>订单管理</cite></a>
                <dl class="layui-nav-child">
                    <dd data-name="order_list"><a lay-href="ex/order_list.php">订单列表</a></dd>
                </dl>
            </li>

            <!-- 财务管理 -->
            <li data-name="finance" class="layui-nav-item">
                <a href="javascript:;" lay-tips="财务管理" lay-direction="2"><i class="layui-icon layui-icon-rmb"></i><cite>财务管理</cite></a>
                <dl class="layui-nav-child">
                    <dd data-name="withdraw_list"><a lay-href="ex/withdraw_list.php">提现管理</a></dd>
                    <dd data-name="financial_list"><a lay-href="ex/financial_list.php">财务明细</a></dd>
                </dl>
            </li>

            <!-- 内容管理 -->
            <li data-name="content" class="layui-nav-item">
                <a href="javascript:;" lay-tips="内容管理" lay-direction="2"><i class="layui-icon layui-icon-chat"></i><cite>内容管理</cite></a>
                <dl class="layui-nav-child">
                    <dd data-name="banner_list"><a lay-href="ex/banner_list.php">轮播图管理</a></dd>
                    <dd data-name="notice_list"><a lay-href="ex/notice_list.php">公告管理</a></dd>
                </dl>
            </li>

            <!-- 系统设置 -->
            <li data-name="system" class="layui-nav-item">
                <a href="javascript:;" lay-tips="系统设置" lay-direction="2"><i class="layui-icon layui-icon-set"></i><cite>系统设置</cite></a>
                <dl class="layui-nav-child">
                    <dd data-name="settings_basic"><a lay-href="basic/settings.php?group=basic">基础设置</a></dd>
                    <dd data-name="settings_order"><a lay-href="basic/settings.php?group=order">订单设置</a></dd>
                    <dd data-name="settings_pay"><a lay-href="basic/settings.php?group=pay">支付设置</a></dd>
                    <dd data-name="settings_wx"><a lay-href="basic/settings.php?group=wx">微信支付</a></dd>
                    <dd data-name="settings_alipay"><a lay-href="basic/settings.php?group=alipay">支付宝支付</a></dd>
                    <dd data-name="settings_sms"><a lay-href="basic/settings.php?group=sms">短信配置</a></dd>
                    <dd data-name="password"><a lay-href="basic/password.php">修改密码</a></dd>
                </dl>
            </li>

        </ul>
    </div></div>

  <!-- 页面标签 -->
      <div class="layadmin-pagetabs" id="LAY_app_tabs">
        <div class="layui-icon layadmin-tabs-control layui-icon-prev" layadmin-event="leftPage"></div>
        <div class="layui-icon layadmin-tabs-control layui-icon-next" layadmin-event="rightPage"></div>
        <div class="layui-icon layadmin-tabs-control layui-icon-down">
          <ul class="layui-nav layadmin-tabs-select" lay-filter="layadmin-pagetabs-nav">
            <li class="layui-nav-item" lay-unselect>
              <a href="javascript:;"></a>
              <dl class="layui-nav-child layui-anim-fadein">
                <dd layadmin-event="closeThisTabs"><a href="javascript:;">关闭当前标签页</a></dd>
                <dd layadmin-event="closeOtherTabs"><a href="javascript:;">关闭其它标签页</a></dd>
                <dd layadmin-event="closeAllTabs"><a href="javascript:;">关闭全部标签页</a></dd>
              </dl>
            </li>
          </ul>
        </div>
        <div class="layui-tab" lay-unauto lay-allowClose="true" lay-filter="layadmin-layout-tabs">
          <ul class="layui-tab-title" id="LAY_app_tabsheader">
            <li lay-id="basic/index.php" lay-attr="basic/index.php" class="layui-this"><i class="layui-icon layui-icon-home"></i></li>  
          </ul>
        </div>
      </div>
      <!-- 主体内容 -->
      <div class="layui-body" id="LAY_app_body">
        <div class="layadmin-tabsbody-item layui-show">
            <iframe src="basic/index.php" frameborder="0" class="layadmin-iframe"></iframe>
        </div>
      </div>
      
      <!-- 辅助元素，一般用于移动设备下遮罩 -->
      <div class="layadmin-body-shade" layadmin-event="shade"></div>
    </div>
  </div>
  <script src="public/layui/layui.js"></script>  
  <script>
  layui.config({
    base: 'public/' //静态资源所在路径
  }).extend({
    index: 'lib/index' //主入口模块
  }).use(['index', 'form'], function(){
    var $ = layui.$
    ,form = layui.form;
    
    //显示登录页面
    $('#LAY-user-login').show();
    
    // 刷新验证码
    window.changing = function() {
        document.getElementById('checkpic').src = "?t=checkcode&" + Math.random();
    }
    
    //提交
    form.on('submit(LAY-user-login-submit)', function(obj){
      // 直接提交表单到?t=login
      // 表单已经设置了action="?t=login"，所以这里不需要额外处理
      return true;
    });
  });
  </script>
</body>
</html>