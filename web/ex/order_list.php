<?php
/**
 * EXHome 快递代取订单管理 - 订单列表
 */
$login = "yes";
require("../data/class.php");
require("../data/config.php");

if (!checkAdminLogin()) {
    header("Location: ../login.php");
    exit;
}

$db = getDbConnection();

// 处理AJAX请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];
    
    switch ($action) {
        case 'cancel':
            $id = intval($_POST['id'] ?? 0);
            if ($id <= 0) jsonResponse(1, '参数错误');
            
            $sql = "UPDATE orders_pickup SET status = 5, update_time = NOW() WHERE id = {$id} AND status IN (0,1)";
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, '订单已取消');
            } else {
                jsonResponse(1, '操作失败: ' . mysqli_error($db));
            }
            break;
    }
}

// 数据接口
if (isset($_GET['t']) && $_GET['t'] == 'data') {
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : 20;
    $offset = ($page - 1) * $limit;
    
    $where = "WHERE 1=1";
    $keyword = isset($_GET['keyword']) ? trim($_GET['keyword']) : '';
    $status = isset($_GET['status']) ? intval($_GET['status']) : -1;
    
    if ($keyword) {
        $keyword_escaped = mysqli_real_escape_string($db, $keyword);
        $where .= " AND (o.order_no LIKE '%{$keyword_escaped}%' OR u.nickname LIKE '%{$keyword_escaped}%' OR u.phone LIKE '%{$keyword_escaped}%')";
    }
    
    if ($status >= 0) {
        $where .= " AND o.status = {$status}";
    }
    
    $sql_count = "SELECT COUNT(*) as count FROM orders_pickup o {$where}";
    $result_count = mysqli_query($db, $sql_count);
    $count = mysqli_fetch_assoc($result_count)['count'];
    
    $sql = "SELECT o.*, u.nickname, u.phone as user_phone 
            FROM orders_pickup o 
            LEFT JOIN users u ON o.user_id = u.id 
            {$where} ORDER BY o.create_time DESC LIMIT {$offset}, {$limit}";
    $result = mysqli_query($db, $sql);
    
    $data = array();
    while ($row = mysqli_fetch_assoc($result)) {
        $row['pickup_codes'] = json_decode($row['pickup_codes'] ?? '[]', true);
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

$setting = getSetting();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>快递代取订单 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">快递代取订单</div>
        <div class="layui-card-body">
            <!-- 搜索表单 -->
            <div class="layui-form layui-form-pane">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">关键词</label>
                        <div class="layui-input-inline">
                            <input type="text" name="keyword" id="keyword" placeholder="订单号/标题/用户" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">状态</label>
                        <div class="layui-input-inline">
                            <select name="status" id="status">
                                <option value="-1">全部</option>
                                <option value="0">待支付</option>
                                <option value="1">待接单</option>
                                <option value="2">已接单</option>
                                <option value="3">配送中</option>
                                <option value="4">已完成</option>
                                <option value="5">已取消</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button class="layui-btn" lay-submit lay-filter="formSearch"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <button type="reset" class="layui-btn layui-btn-primary"><i class="layui-icon layui-icon-refresh"></i> 重置</button>
                    </div>
                </div>
            </div>
            
            <!-- 数据表格 -->
            <table class="layui-hide" id="orderTable" lay-filter="orderTable"></table>
        </div>
    </div>
</div>

<script type="text/html" id="statusTpl">
    {{# if(d.status == 0){ }}
    <span class="layui-badge layui-bg-orange">待支付</span>
    {{# } else if(d.status == 1){ }}
    <span class="layui-badge layui-bg-blue">待接单</span>
    {{# } else if(d.status == 2){ }}
    <span class="layui-badge layui-bg-cyan">已接单</span>
    {{# } else if(d.status == 3){ }}
    <span class="layui-badge layui-bg-green">配送中</span>
    {{# } else if(d.status == 4){ }}
    <span class="layui-badge layui-bg-gray">已完成</span>
    {{# } else if(d.status == 5){ }}
    <span class="layui-badge layui-bg-gray">已取消</span>
    {{# } }}
</script>

<script type="text/html" id="userTpl">
    <div>
        <div>{{d.nickname || '未知用户'}}</div>
        {{# if(d.user_phone){ }}
        <div style="color: #666; font-size: 12px;">{{d.user_phone}}</div>
        {{# } }}
    </div>
</script>

<script type="text/html" id="orderInfoTpl">
    <div>
        <div style="font-weight: bold;">代取快递，共{{d.package_count || 1}}个</div>
        <div style="color: #666; font-size: 12px;">
            {{d.weight || 0}}kg
            {{# if(d.pickup_codes && d.pickup_codes.length > 0){ }}
            / 取件码:{{d.pickup_codes.length}}个
            {{# } }}
        </div>
    </div>
</script>

<script type="text/html" id="amountTpl">
    <div style="color: #f44336; font-weight: bold;">¥{{d.pay_amount}}</div>
    <div style="color: #999; font-size: 12px;">
        {{# if(d.pay_type == 1){ }}微信支付{{# } else if(d.pay_type == 2){ }}支付宝支付{{# } else if(d.pay_type == 9){ }}余额支付{{# } else { }}未支付{{# } }}
    </div>
</script>

<script type="text/html" id="tableOperate">
    <a class="layui-btn layui-btn-normal layui-btn-xs" lay-event="detail">详情</a>
    {{# if(d.status == 1){ }}
    <a class="layui-btn layui-btn-danger layui-btn-xs" lay-event="cancel">取消</a>
    {{# } }}
</script>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['table', 'form', 'layer'], function(){
    var table = layui.table;
    var form = layui.form;
    var layer = layui.layer;
    
    // 渲染表格
    var tableIns = table.render({
        elem: '#orderTable',
        url: '?t=data',
        page: true,
        limit: 20,
        limits: [10, 20, 50, 100],
        cols: [[
            {field: 'id', title: 'ID', width: 70, sort: true},
            {field: 'order_no', title: '订单号', width: 180},
            {field: 'package_count', title: '订单信息', minWidth: 150, templet: '#orderInfoTpl'},
            {field: 'nickname', title: '用户信息', width: 120, templet: '#userTpl'},
            {field: 'pay_amount', title: '金额', width: 100, templet: '#amountTpl'},
            {field: 'status', title: '状态', width: 80, align: 'center', templet: '#statusTpl'},
            {field: 'create_time', title: '创建时间', width: 160},
            {title: '操作', width: 120, align: 'center', toolbar: '#tableOperate'}
        ]],
        response: {
            statusCode: 0
        },
        parseData: function(res) {
            return {
                "code": res.code,
                "msg": res.msg,
                "count": res.count,
                "data": res.data
            };
        }
    });
    
    // 搜索
    form.on('submit(formSearch)', function(data){
        tableIns.reload({
            where: {
                keyword: $('#keyword').val(),
                status: $('#status').val()
            },
            page: {curr: 1}
        });
        return false;
    });
    
    // 监听工具条
    table.on('tool(orderTable)', function(obj){
        var data = obj.data;
        
        if(obj.event === 'detail'){
            // 查看详情
            showDetail(data);
        } else if(obj.event === 'cancel'){
            layer.confirm('确定要取消该订单吗？', function(index){
                $.ajax({
                    url: '',
                    type: 'POST',
                    data: {
                        action: 'cancel',
                        id: data.id
                    },
                    dataType: 'json',
                    success: function(res){
                        if(res.code === 0){
                            layer.msg('取消成功', {icon: 1});
                            tableIns.reload();
                        } else {
                            layer.msg(res.msg, {icon: 2});
                        }
                    }
                });
                layer.close(index);
            });
        }
    });
    
    function showDetail(order) {
        var statusText = {
            0: '<span class="layui-badge layui-bg-orange">待支付</span>',
            1: '<span class="layui-badge layui-bg-blue">待接单</span>',
            2: '<span class="layui-badge layui-bg-cyan">已接单</span>',
            3: '<span class="layui-badge layui-bg-green">配送中</span>',
            4: '<span class="layui-badge layui-bg-gray">已完成</span>',
            5: '<span class="layui-badge layui-bg-gray">已取消</span>',
        };
        
        var payTypeText = {
            0: '未支付',
            1: '微信支付',
            2: '支付宝支付',
            9: '余额支付',
        };
        
        var html = '<div style="padding: 20px; max-height: 500px; overflow-y: auto;">';
        
        html += '<table class="layui-table" style="margin: 0;">';
        html += '<tr><td style="width: 100px; background: #f8f8f8;">订单号</td><td>' + order.order_no + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">订单状态</td><td>' + statusText[order.status] + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">订单信息</td><td>代取快递，共' + (order.package_count || 1) + '个</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">用户信息</td><td>' + (order.nickname || '未知用户') + ' ' + (order.user_phone || '') + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">包裹数量</td><td>' + (order.package_count || 1) + ' 件</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">包裹重量</td><td>' + (order.weight || 0) + ' kg</td></tr>';
        
        if (order.pickup_codes && order.pickup_codes.length > 0) {
            html += '<tr><td style="background: #f8f8f8;">取件码</td><td>';
            html += '<div style="display: flex; flex-direction: column; gap: 8px;">';
            order.pickup_codes.forEach(function(item) {
                if (typeof item === 'object') {
                    html += '<div style="background: #f5f5f5; padding: 8px 12px; border-radius: 4px;">';
                    html += '<span style="font-weight: bold; color: #333;">' + (item.code || '-') + '</span>';
                    if (item.location) {
                        html += '<span style="color: #666; margin-left: 10px;">' + item.location + '</span>';
                    }
                    html += '</div>';
                } else {
                    html += '<div style="background: #f5f5f5; padding: 8px 12px; border-radius: 4px;">';
                    html += '<span style="font-weight: bold; color: #333;">' + item + '</span>';
                    html += '</div>';
                }
            });
            html += '</div></td></tr>';
        }
        
        html += '<tr><td style="background: #f8f8f8;">取件地址</td><td>' + (order.pickup_address || '-') + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">送达地址</td><td>' + (order.delivery_address || '-') + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">联系人</td><td>' + (order.contact_name || '-') + ' ' + (order.contact_phone || '') + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">应付金额</td><td style="color: #f44336; font-weight: bold;">¥' + order.pay_amount + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">支付方式</td><td>' + (payTypeText[order.pay_type] || '未知') + '</td></tr>';
        html += '<tr><td style="background: #f8f8f8;">创建时间</td><td>' + order.create_time + '</td></tr>';
        
        if (order.remark) {
            html += '<tr><td style="background: #f8f8f8;">备注</td><td style="color: #ff9800;">' + order.remark + '</td></tr>';
        }
        
        html += '</table>';
        html += '</div>';
        
        layer.open({
            type: 1,
            title: '订单详情',
            area: ['600px', 'auto'],
            maxHeight: 600,
            content: html,
            btn: ['关闭'],
            yes: function(index) {
                layer.close(index);
            }
        });
    }
});
</script>

</body>
</html>
