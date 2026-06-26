<?php 
require("../data/class.php");

$t = isset($_GET['t']) ? $_GET['t'] : '';
$key = isset($_GET['key']) ? $_GET['key'] : '';
$page = isset($_GET['page']) ? intval($_GET['page']) : 1;

// 删除模块
if (isset($_GET['e']) && $_GET['e'] == "del") {
    $del_id = intval($_GET['del_id']);
    if($del_id > 0) {
        $sql = "DELETE FROM wx_a16 WHERE id='$del_id' LIMIT 1";
        mysqli_query($conn, $sql);
    }
    if (!empty($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) == 'xmlhttprequest') {
        header('Content-Type: application/json');
        echo json_encode(['code' => 0, 'msg' => '删除成功']);
        exit;
    }
    print "<script>location.href='wx_a16_list.php?key=".$key."&page=".$page."';</script>";
    exit;
}

// 批量重置使用日期模块
if ($_SERVER['REQUEST_METHOD'] == 'POST' && isset($_POST['action']) && $_POST['action'] == 'reset_last') {
    $sql = "UPDATE wx_a16 SET last = NULL WHERE status != -1";
    if (mysqli_query($conn, $sql)) {
        $affected_rows = mysqli_affected_rows($conn);
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(array(
            'code' => 0,
            'msg' => '重置成功',
            'affected_rows' => $affected_rows
        ), JSON_UNESCAPED_UNICODE);
    } else {
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(array(
            'code' => 1,
            'msg' => '重置失败: ' . mysqli_error($conn)
        ), JSON_UNESCAPED_UNICODE);
    }
    exit;
}

// 批量启用所有账号模块
if ($_SERVER['REQUEST_METHOD'] == 'POST' && isset($_POST['action']) && $_POST['action'] == 'enable_all') {
    $sql = "UPDATE wx_a16 SET status = 0, remarks = '' WHERE status = -1";
    if (mysqli_query($conn, $sql)) {
        $affected_rows = mysqli_affected_rows($conn);
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(array(
            'code' => 0,
            'msg' => '启用成功',
            'affected_rows' => $affected_rows
        ), JSON_UNESCAPED_UNICODE);
    } else {
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(array(
            'code' => 1,
            'msg' => '启用失败: ' . mysqli_error($conn)
        ), JSON_UNESCAPED_UNICODE);
    }
    exit;
}

// 批量导入模块
if ($_SERVER['REQUEST_METHOD'] == 'POST' && isset($_POST['action']) && $_POST['action'] == 'batch_import') {
    $import_data = isset($_POST['import_data']) ? trim($_POST['import_data']) : '';
    $lines = explode("\n", $import_data);
    $success_count = 0;
    $error_count = 0;
    $errors = array();
    
    foreach ($lines as $line) {
        $line = trim($line);
        if (empty($line)) continue;
        
        $parts = explode('----', $line);
        if (count($parts) >= 3) {
            $wxid = mysqli_real_escape_string($conn, trim($parts[0]));
            $password = mysqli_real_escape_string($conn, trim($parts[1]));
            $a16 = mysqli_real_escape_string($conn, trim($parts[2]));
            
            if (!empty($wxid) && !empty($password) && !empty($a16)) {
                $sql = "INSERT INTO wx_a16 (wxid, password, a16, status) VALUES ('$wxid', '$password', '$a16', 0)";
                if (mysqli_query($conn, $sql)) {
                    $success_count++;
                } else {
                    $error_count++;
                    $errors[] = "导入失败: " . mysqli_error($conn);
                }
            } else {
                $error_count++;
                $errors[] = "数据不完整: " . $line;
            }
        } else {
            $error_count++;
            $errors[] = "格式错误: " . $line;
        }
    }
    
    header('Content-Type: application/json;charset=utf-8');
    echo json_encode(array(
        'code' => 0,
        'msg' => '导入完成',
        'success_count' => $success_count,
        'error_count' => $error_count,
        'errors' => $errors
    ), JSON_UNESCAPED_UNICODE);
    exit;
}

// 数据接口
if ($t == "data") {
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : 20;
    $status_filter = isset($_GET['status_filter']) ? intval($_GET['status_filter']) : null;
    
    $where = "1=1";
    if ($key != '') {
        $where .= " AND (wxid LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR a16 LIKE '%" . mysqli_real_escape_string($conn, $key) . "%')";
    }
    if ($status_filter !== null) {
        $where .= " AND status = " . intval($status_filter);
    }

    $sql_count = "SELECT COUNT(*) as count FROM wx_a16 WHERE $where";
    $result_count = mysqli_query($conn, $sql_count);
    $row_count = mysqli_fetch_assoc($result_count);
    $count = $row_count['count'];

    $start = ($page - 1) * $limit;
    $sql = "SELECT * FROM wx_a16 WHERE $where ORDER BY id DESC LIMIT $start, $limit";
    $result = mysqli_query($conn, $sql);

    $data = array();
    while($row = mysqli_fetch_assoc($result)) {
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
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>A16账号</title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card layadmin-header">
        <div class="layui-breadcrumb" lay-filter="breadcrumb">
            <a lay-href="">主页</a>
            <a><cite>A16账号</cite></a>
        </div>
    </div>
    
    <div class="layui-row layui-col-space15">
        <div class="layui-col-md12">
            <div class="layui-card">
                <div class="layui-card-body">
                    <div class="layui-row">
                        <div class="layui-col-md12">
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: -10px;">
                                <div class="layui-btn-container" style="margin: 0;">
                                    <button class="layui-btn" id="allBtn" style="background-color: #1E9FFF; color: #fff;">所有账号</button>
                                    <button class="layui-btn" id="disabledBtn" style="background-color: #f4f4f5; color: #606266;">禁用账号</button>
                                    <button class="layui-btn layui-bg-green" id="addBtn">添加账号</button>
                                    <button class="layui-btn layui-btn-warm" id="batchImportBtn">批量导入</button>
                                    <button class="layui-btn layui-btn-danger" id="resetLastBtn">重置日期</button>
                                    <button class="layui-btn layui-btn-normal" id="enableAllBtn">启用所有账号</button>
                                </div>
                                
                                <div class="user-table-reload-btn">
                                    <div class="layui-inline">
                                        <input class="layui-input" name="key" id="key-search" placeholder="wxid/Key" value="<?php echo htmlspecialchars($key); ?>">
                                    </div>
                                    <button class="layui-btn" data-type="reload">搜索</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <table class="layui-table" id="data-table" lay-filter="data-table"></table>
                </div>
            </div>
        </div>
    </div>
</div>

<script type="text/html" id="status-bar">
    {{#  if(d.status == -1){ }}
        <span class="layui-badge layui-bg-red">禁用</span>
    {{#  } else if(d.status == 0){ }}
        <span class="layui-badge layui-bg-green">启用</span>
    {{#  } else if(d.status == 1){ }}
        <span class="layui-badge layui-bg-blue">已用</span>
    {{#  } }}
</script>

<script type="text/html" id="proxy-bar">
    {{#  if(d.proxy && d.proxy != ''){ }}
        <span class="layui-badge layui-bg-blue">启用</span>
    {{#  } else { }}
        <span class="layui-badge layui-bg-gray">未启用</span>
    {{#  } }}
</script>

<script type="text/html" id="operate-bar">
    <a class="layui-btn layui-btn-xs layui-btn-normal" lay-event="edit">编辑</a>
    <a class="layui-btn layui-btn-danger layui-btn-xs" lay-event="del">删除</a>
</script>

<script src="../public/layui/layui.js"></script>
<script>
layui.config({
    base: '../public/'
}).use(['table', 'layer', 'form'], function(){
    var table = layui.table
    ,layer = layui.layer
    ,$ = layui.$;
    
    // 当前筛选状态：null-所有账号, -1-禁用账号
    var currentStatusFilter = null;
    
    // 切换按钮选中状态的函数
    function setActiveButton(activeBtnId) {
        // 设置选中按钮的样式（蓝色）
        // 设置未选中按钮的样式（灰色）
        if (activeBtnId === 'allBtn') {
            $('#allBtn').css({'background-color': '#1E9FFF', 'color': '#fff', 'border-color': '#1E9FFF'});
            $('#disabledBtn').css({'background-color': '#f4f4f5', 'color': '#606266', 'border-color': '#dcdfe6'});
        } else if (activeBtnId === 'disabledBtn') {
            $('#disabledBtn').css({'background-color': '#1E9FFF', 'color': '#fff', 'border-color': '#1E9FFF'});
            $('#allBtn').css({'background-color': '#f4f4f5', 'color': '#606266', 'border-color': '#dcdfe6'});
        }
    }
  
    var dataTable = table.render({
        elem: '#data-table'
        ,url: '?t=data'
        ,page: true
        ,limit: 20
        ,cols: [[
            {field:'id', width:80, title: 'ID'}
            ,{field:'wxid', title: '微信ID', minWidth: 150}
            ,{field:'password', title: '密码', width: 120}
            ,{field:'a16', title: 'A16', minWidth: 150}
            ,{field:'proxy', title: '代理', width: 100, templet: '#proxy-bar'}
            ,{field:'status', title: '状态', width: 80, templet: '#status-bar'}
            ,{field:'remarks', title: '备注', minWidth: 150}
            ,{field:'created_at', title: '创建时间', width: 170, sort: false}
            ,{field:'last', title: '最后使用', width: 170, sort: false}
            ,{width:120, align:'center', toolbar: '#operate-bar', title: '操作'}
        ]]
    });
    
    // 初始化默认选中"所有账号"
    setActiveButton('allBtn');
    
    // 获取表格刷新参数的辅助函数
    function getTableWhereParams() {
        var keySearch = $('#key-search');
        var whereParams = { key: keySearch.val() };
        // 只有在筛选禁用账号时才添加 status_filter 参数
        if (currentStatusFilter === -1) {
            whereParams.status_filter = -1;
        }
        return whereParams;
    }
    
    var active = {
        reload: function(){
            table.reload('data-table', {
                page: { curr: 1 }
                ,where: getTableWhereParams()
            });
        }
    };
    
    $('.user-table-reload-btn .layui-btn').on('click', function(){
        var type = $(this).data('type');
        active[type] ? active[type].call(this) : '';
    });
    
    // 所有账号按钮
    $('#allBtn').on('click', function(){
        currentStatusFilter = null;
        var keySearch = $('#key-search');
        table.reload('data-table', {
            page: { curr: 1 }
            ,where: { key: keySearch.val() }
        });
        setActiveButton('allBtn');
    });
    
    // 禁用账号按钮
    $('#disabledBtn').on('click', function(){
        currentStatusFilter = -1;
        var keySearch = $('#key-search');
        table.reload('data-table', {
            page: { curr: 1 }
            ,where: { key: keySearch.val(), status_filter: -1 }
        });
        setActiveButton('disabledBtn');
    });
    
    $('#addBtn').on('click', function(){
        layer.open({
            type: 2,
            title: '添加微信',
            content: 'wx_a16_add.php',
            area: ['660px', '550px'],
            shadeClose: false,
            end: function(){
                // 弹窗关闭后刷新表格，保持当前筛选状态
                table.reload('data-table', {
                    where: getTableWhereParams()
                });
            }
        });
    });

    $('#batchImportBtn').on('click', function(){
        layer.open({
            type: 1,
            title: '批量导入微信',
            content: '<div style="padding: 20px;">' +
                '<div style="margin-bottom: 10px; color: #666;">格式说明：wxid----password----key（每行一条）</div>' +
                '<textarea id="batchImportData" class="layui-textarea" style="height: 300px;" placeholder="例如：\nwxid_tvc6oyyodaox22----wwww112233----A01ff4339d5a45e8\nwxid_eocevuq3fvcb22----wwww112233----A08e6a3eb4cb7896"></textarea>' +
                '<div style="margin-top: 15px; text-align: right;">' +
                '<button class="layui-btn" id="confirmImport">确认导入</button>' +
                '<button class="layui-btn layui-btn-primary" id="cancelImport">取消</button>' +
                '</div>' +
                '</div>',
            area: ['700px', '500px'],
            shadeClose: false,
            success: function(layero, index){
                $('#confirmImport').on('click', function(){
                    var importData = $('#batchImportData').val();
                    if (!importData.trim()) {
                        layer.msg('请输入要导入的数据');
                        return;
                    }
                    
                    var loadIndex = layer.load(2);
                    
                    $.ajax({
                        url: '?action=batch_import',
                        type: 'POST',
                        data: { action: 'batch_import', import_data: importData },
                        dataType: 'json',
                        success: function(res){
                            layer.close(loadIndex);
                            if (res.code === 0) {
                                var msg = '导入完成！成功: ' + res.success_count + '，失败: ' + res.error_count;
                                if (res.errors.length > 0) {
                                    msg += '\n\n错误详情:\n' + res.errors.join('\n');
                                }
                                layer.msg(msg, {icon: 1, time: 3000});
                                table.reload('data-table', {
                                    where: getTableWhereParams()
                                });
                                layer.close(index);
                            } else {
                                layer.msg('导入失败', {icon: 2});
                            }
                        },
                        error: function(){
                            layer.close(loadIndex);
                            layer.msg('请求失败', {icon: 2});
                        }
                    });
                });
                
                $('#cancelImport').on('click', function(){
                    layer.close(index);
                });
            }
        });
    });

    $('#resetLastBtn').on('click', function(){
        layer.confirm('确定要批量重置所有条目的使用日期吗？此操作不可恢复！', {icon: 3, title:'提示'}, function(index){
            var loadIndex = layer.load(2);
            $.ajax({
                url: '?',
                type: 'POST',
                data: { action: 'reset_last' },
                dataType: 'json',
                success: function(res){
                    layer.close(loadIndex);
                    if(res.code === 0){
                        layer.msg('重置成功！共重置 ' + res.affected_rows + ' 条记录', {icon: 1});
                        table.reload('data-table', {
                            where: getTableWhereParams()
                        });
                    } else {
                        layer.msg('重置失败: ' + res.msg, {icon: 2});
                    }
                },
                error: function(){
                    layer.close(loadIndex);
                    layer.msg('请求失败', {icon: 2});
                }
            });
            layer.close(index);
        });
    });

    // 启用所有账号按钮
    $('#enableAllBtn').on('click', function(){
        layer.confirm('确定要启用所有禁用的账号吗？', {icon: 3, title:'提示'}, function(index){
            var loadIndex = layer.load(2);
            $.ajax({
                url: '?',
                type: 'POST',
                data: { action: 'enable_all' },
                dataType: 'json',
                success: function(res){
                    layer.close(loadIndex);
                    if(res.code === 0){
                        layer.msg('启用成功！共启用 ' + res.affected_rows + ' 条记录', {icon: 1});
                        table.reload('data-table', {
                            where: getTableWhereParams()
                        });
                    } else {
                        layer.msg('启用失败: ' + res.msg, {icon: 2});
                    }
                },
                error: function(){
                    layer.close(loadIndex);
                    layer.msg('请求失败', {icon: 2});
                }
            });
            layer.close(index);
        });
    });

    table.on('tool(data-table)', function(obj){
        var data = obj.data;
        if(obj.event === 'del'){
            layer.confirm('确定要删除吗？', function(index){
                $.ajax({
                    url: '?e=del&del_id=' + data.id,
                    type: 'GET',
                    dataType: 'json',
                    success: function(res){
                        if(res.code === 0){
                        layer.msg('删除成功');
                        table.reload('data-table', {
                            where: getTableWhereParams()
                        });
                    } else {
                            layer.msg('删除失败');
                        }
                    }
                });
                layer.close(index);
            });
        } else if(obj.event === 'edit'){
            layer.open({
                type: 2,
                title: '编辑微信',
                content: 'wx_a16_add.php?id=' + data.id,
                area: ['660px', '550px'],
                shadeClose: false,
                end: function(){
                    // 弹窗关闭后刷新表格，保持当前筛选状态
                    table.reload('data-table', {
                        where: getTableWhereParams()
                    });
                }
            });
        }
    });
});
</script>
</body>
</html>
