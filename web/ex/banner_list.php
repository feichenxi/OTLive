<?php
/**
 * EXHome 广告管理 - 广告列表
 */
$login = "yes";
require("../data/class.php");
require("../data/config.php");

// 检查登录
if (!checkAdminLogin()) {
    header("Location: ../login.php");
    exit;
}

$db = getDbConnection();

// 定义位置选项
$positionOptions = [
    'index' => '首页轮播图',
    'category' => '分类页广告',
    'order' => '下单页广告',
    'mine' => '我的页广告',
    'popup' => '弹窗广告',
    'login' => '登录轮播图'
];

// 处理AJAX请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];
    
    switch ($action) {
        case 'toggle_status':
            $id = intval($_POST['id'] ?? 0);
            $status = intval($_POST['status'] ?? 0);
            
            if ($id <= 0) {
                jsonResponse(1, '参数错误');
            }
            
            $sql = "UPDATE banners SET status = {$status}, update_time = NOW() WHERE id = {$id}";
            
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, '操作成功');
            } else {
                jsonResponse(1, '操作失败: ' . mysqli_error($db));
            }
            break;
            
        case 'delete':
            $id = intval($_POST['id'] ?? 0);
            
            if ($id <= 0) {
                jsonResponse(1, '参数错误');
            }
            
            // 获取图片路径并删除
            $sql = "SELECT image FROM banners WHERE id = {$id}";
            $result = mysqli_query($db, $sql);
            $banner = mysqli_fetch_assoc($result);
            if ($banner && !empty($banner['image'])) {
                deleteBannerImage($banner['image']);
            }
            
            $sql = "DELETE FROM banners WHERE id = {$id}";
            
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, '删除成功');
            } else {
                jsonResponse(1, '删除失败: ' . mysqli_error($db));
            }
            break;
    }
}

// 数据接口
if (isset($_GET['t']) && $_GET['t'] == 'data') {
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : 20;
    $offset = ($page - 1) * $limit;
    
    // 搜索条件
    $where = "WHERE 1=1";
    $status = isset($_GET['status']) ? intval($_GET['status']) : -1;
    $position = isset($_GET['position']) ? trim($_GET['position']) : '';
    
    if ($status >= 0) {
        $where .= " AND status = {$status}";
    }
    if (!empty($position)) {
        $position_escaped = mysqli_real_escape_string($db, $position);
        $where .= " AND position = '{$position_escaped}'";
    }
    
    // 获取总记录数
    $sql = "SELECT COUNT(*) as count FROM banners {$where}";
    $result = mysqli_query($db, $sql);
    $count = mysqli_fetch_assoc($result)['count'];
    
    // 获取轮播图列表
    $sql = "SELECT * FROM banners {$where} ORDER BY position ASC, sort DESC, id DESC LIMIT {$offset}, {$limit}";
    $result = mysqli_query($db, $sql);
    $data = array();
    while ($row = mysqli_fetch_assoc($result)) {
        $data[] = $row;
    }
    
    header('Content-Type: application/json;charset=utf-8');
    echo json_encode(array(
        'code' => 0,
        'msg' => '',
        'count' => $count,
        'data' => $data
    ), JSON_UNESCAPED_UNICODE);
    exit;
}

// 加载系统设置
$setting = getSetting();

/**
 * 删除轮播图图片
 */
function deleteBannerImage($imageUrl) {
    $filepath = '../' . $imageUrl;
    if (file_exists($filepath) && strpos($imageUrl, 'uploads/banner/') === 0) {
        @unlink($filepath);
    }
}
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>广告管理 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
    <style>
        .banner-img { width: 100px; height: 60px; object-fit: cover; border-radius: 4px; cursor: pointer; }
        .position-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
        .position-index { background: #e6f7ff; color: #1890ff; }
        .position-category { background: #f6ffed; color: #52c41a; }
        .position-order { background: #fff7e6; color: #fa8c16; }
        .position-mine { background: #f9f0ff; color: #722ed1; }
        .position-popup { background: #fff1f0; color: #f5222d; }
        .position-login { background: #e6fffb; color: #13c2c2; }
    </style>
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">广告管理</div>
        <div class="layui-card-body">
            <!-- 搜索表单 -->
            <div class="layui-form layui-form-pane">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">位置</label>
                        <div class="layui-input-inline">
                            <select name="position" id="position-search" lay-search>
                                <option value="">全部位置</option>
                                <?php foreach ($positionOptions as $key => $name): ?>
                                <option value="<?php print $key; ?>"><?php print $name; ?></option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">状态</label>
                        <div class="layui-input-inline">
                            <select name="status" id="status-search">
                                <option value="-1">全部</option>
                                <option value="1">显示</option>
                                <option value="0">隐藏</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button type="button" class="layui-btn layui-btn-normal" id="searchBtn"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <button type="button" class="layui-btn layui-btn-primary" id="resetBtn">重置</button>
                        <button type="button" class="layui-btn layui-btn-success" id="addBtn"><i class="layui-icon layui-icon-add-1"></i> 新增广告</button>
                    </div>
                </div>
            </div>

            <!-- 数据表格 -->
            <table class="layui-table" id="data-table" lay-filter="data-table"></table>
        </div>
    </div>
</div>

<!-- 状态模板 -->
<script type="text/html" id="status-tpl">
    {{# if(d.status == 1){ }}
        <span class="layui-badge layui-bg-green">显示</span>
    {{# } else { }}
        <span class="layui-badge layui-bg-gray">隐藏</span>
    {{# } }}
</script>

<!-- 位置模板 -->
<script type="text/html" id="position-tpl">
    {{# 
        var positionMap = {
            'index': {name: '首页轮播图', class: 'position-index'},
            'category': {name: '分类页广告', class: 'position-category'},
            'order': {name: '下单页广告', class: 'position-order'},
            'mine': {name: '我的页广告', class: 'position-mine'},
            'popup': {name: '弹窗广告', class: 'position-popup'},
            'login': {name: '登录轮播图', class: 'position-login'}
        };
        var pos = positionMap[d.position] || {name: '未知', class: ''};
    }}
    <span class="position-tag {{ pos.class }}">{{ pos.name }}</span>
</script>

<!-- 图片模板 -->
<script type="text/html" id="image-tpl">
    <img src="../{{ d.image }}" class="banner-img" lay-event="preview" onerror="this.src='../public/images/default.png'">
</script>

<!-- 操作模板 -->
<script type="text/html" id="operate-bar">
    <a class="layui-btn layui-btn-xs layui-btn-normal" lay-event="edit">编辑</a>
    {{# if(d.status == 1){ }}
        <a class="layui-btn layui-btn-xs layui-btn-danger" lay-event="hide">隐藏</a>
    {{# } else { }}
        <a class="layui-btn layui-btn-xs layui-btn-success" lay-event="show">显示</a>
    {{# } }}
    <a class="layui-btn layui-btn-xs layui-btn-danger" lay-event="del">删除</a>
</script>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['table', 'layer', 'form'], function(){
    var table = layui.table;
    var layer = layui.layer;
    var form = layui.form;
    var $ = layui.$;
    
    // 渲染表格
    var dataTable = table.render({
        elem: '#data-table'
        ,url: '?t=data'
        ,page: true
        ,limit: 20
        ,cols: [[
            {field:'id', width:60, title: 'ID'}
            ,{field:'image', title: '图片', width: 120, templet: '#image-tpl'}
            ,{field:'title', title: '标题', minWidth: 150}
            ,{field:'position', title: '位置', width: 120, templet: '#position-tpl'}
            ,{field:'link_url', title: '链接', minWidth: 150, templet: function(d){
                return d.link_url ? (d.link_url.length > 25 ? d.link_url.substring(0, 25) + '...' : d.link_url) : '-';
            }}
            ,{field:'sort', title: '排序', width: 70}
            ,{field:'status', title: '状态', width: 70, templet: '#status-tpl'}
            ,{field:'create_time', title: '创建时间', width: 150}
            ,{width:180, align:'center', toolbar: '#operate-bar', title: '操作'}
        ]]
    });
    
    // 搜索
    $('#searchBtn').on('click', function(){
        var position = $('#position-search').val();
        var status = $('#status-search').val();
        table.reload('data-table', {
            page: { curr: 1 }
            ,where: { 
                position: position,
                status: status
            }
        });
    });
    
    // 重置
    $('#resetBtn').on('click', function(){
        $('#position-search').val('');
        $('#status-search').val('-1');
        form.render('select');
        table.reload('data-table', {
            page: { curr: 1 }
            ,where: { 
                position: '',
                status: -1
            }
        });
    });
    
    // 新增
    $('#addBtn').on('click', function(){
        layer.open({
            type: 2,
            title: '新增轮播图',
            content: 'banner_add.php',
            area: ['650px', '580px'],
            shadeClose: false
        });
    });
    
    // 表格工具条事件
    table.on('tool(data-table)', function(obj){
        var data = obj.data;
        
        if(obj.event === 'edit'){
            layer.open({
                type: 2,
                title: '编辑轮播图',
                content: 'banner_add.php?id=' + data.id,
                area: ['650px', '580px'],
                shadeClose: false
            });
        } else if(obj.event === 'preview'){
            layer.photos({
                photos: {
                    data: [{ src: '../' + data.image }]
                },
                shade: 0.5
            });
        } else if(obj.event === 'show'){
            toggleStatus(data.id, 1);
        } else if(obj.event === 'hide'){
            toggleStatus(data.id, 0);
        } else if(obj.event === 'del'){
            layer.confirm('确定要删除该轮播图吗？删除后不可恢复！', function(index){
                $.ajax({
                    url: 'banner_list.php',
                    type: 'POST',
                    data: {action: 'delete', id: data.id},
                    dataType: 'json',
                    success: function(res){
                        if(res.code === 0){
                            layer.msg('删除成功', {icon: 1});
                            table.reload('data-table');
                        } else {
                            layer.msg(res.msg || '删除失败', {icon: 2});
                        }
                    }
                });
                layer.close(index);
            });
        }
    });
    
    // 切换状态
    function toggleStatus(id, status) {
        var msg = status == 1 ? '确定要显示该轮播图吗？' : '确定要隐藏该轮播图吗？';
        layer.confirm(msg, function(index){
            $.ajax({
                url: 'banner_list.php',
                type: 'POST',
                data: {action: 'toggle_status', id: id, status: status},
                dataType: 'json',
                success: function(res){
                    if(res.code === 0){
                        layer.msg('操作成功', {icon: 1});
                        table.reload('data-table');
                    } else {
                        layer.msg(res.msg || '操作失败', {icon: 2});
                    }
                }
            });
            layer.close(index);
        });
    }
});
</script>

</body>
</html>
