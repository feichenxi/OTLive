<?php
require("../data/class.php");
require("../public/PHPExcel/Classes/PHPExcel.php");

$t = isset($_GET['t']) ? $_GET['t'] : '';

if ($t == "upload") {
    if (!isset($_FILES['excel_file']) || $_FILES['excel_file']['error'] != 0) {
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(['code' => 1, 'msg' => '文件上传失败']);
        exit;
    }

    $file = $_FILES['excel_file'];
    $fileName = $file['name'];
    $fileTmp = $file['tmp_name'];
    $fileExt = strtolower(pathinfo($fileName, PATHINFO_EXTENSION));

    if ($fileExt != 'xlsx' && $fileExt != 'xls') {
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(['code' => 1, 'msg' => '只支持Excel文件格式(xlsx/xls)']);
        exit;
    }

    $uploadDir = '../upload/' . date('Ymd') . '/';
    if (!is_dir($uploadDir)) {
        mkdir($uploadDir, 0777, true);
    }

    $newFileName = time() . '_' . rand(1000, 9999) . '.' . $fileExt;
    $filePath = $uploadDir . $newFileName;

    if (!move_uploaded_file($fileTmp, $filePath)) {
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(['code' => 1, 'msg' => '文件保存失败']);
        exit;
    }

    $errorMsg = null;
    $groups = parseExcelFile($filePath, $errorMsg);

    if (empty($groups)) {
        $debugInfo = array();
        $debugInfo['filePath'] = $filePath;
        $debugInfo['fileExists'] = file_exists($filePath);
        $debugInfo['fileSize'] = filesize($filePath);
        $debugInfo['fileExt'] = strtolower(pathinfo($filePath, PATHINFO_EXTENSION));
        $debugInfo['errorMsg'] = $errorMsg;
        
        ob_clean();
        header('Content-Type: application/json;charset=utf-8');
        echo json_encode(['code' => 1, 'msg' => 'Excel文件解析失败或没有有效数据', 'debug' => $debugInfo]);
        exit;
    }

    ob_clean();
    header('Content-Type: application/json;charset=utf-8');
    echo json_encode(['code' => 0, 'msg' => '解析成功', 'data' => $groups]);
    exit;
}

function parseExcelFile($filePath, &$errorMsg = null) {
    $groups = array();
    
    try {
        $objPHPExcel = PHPExcel_IOFactory::load($filePath);
        $sheet = $objPHPExcel->getActiveSheet();
        $highestRow = $sheet->getHighestRow();
        $highestColumn = $sheet->getHighestColumn();
        
        $currentGroup = array();
        $headerProcessed = false;
        $debugLog = array();
        
        for ($row = 1; $row <= $highestRow; $row++) {
            $rowData = array();
            $hasData = false;
            $hasKeyData = false;
            
            for ($col = 'A'; $col <= $highestColumn; $col++) {
                $cell = $sheet->getCell($col . $row);
                $cellValue = $cell->getValue();
                
                $calculatedValue = $cell->getOldCalculatedValue();
                if ($calculatedValue !== null && $calculatedValue !== '') {
                    $cellValue = $calculatedValue;
                }
                
                if ($cellValue !== null && trim($cellValue) !== '') {
                    $hasData = true;
                }
                $rowData[] = trim($cellValue);
            }
            
            $debugLog[] = array(
                'row' => $row,
                'hasData' => $hasData,
                'data' => $rowData
            );
            
            if (count($rowData) >= 2 && trim($rowData[1]) !== '') {
                $hasKeyData = true;
            }
            
            if (!$hasKeyData) {
                if (!empty($currentGroup)) {
                    $groups[] = $currentGroup;
                    $currentGroup = array();
                }
                continue;
            }
            
            if (!$headerProcessed) {
                $headerProcessed = true;
                continue;
            }
            
            if (count($rowData) >= 4 && trim($rowData[1]) !== '') {
                $person = array(
                    'ticket_name' => trim($rowData[0]),
                    'name' => trim($rowData[1]),
                    'id_type' => trim($rowData[2]),
                    'id_num' => trim($rowData[3])
                );
                $currentGroup[] = $person;
            }
        }
        
        if (!empty($currentGroup)) {
            $groups[] = $currentGroup;
        }
        
        error_log('Excel解析调试: ' . json_encode($debugLog, JSON_UNESCAPED_UNICODE));
    } catch (Exception $e) {
        $errorMsg = 'PHPExcel解析错误: ' . $e->getMessage();
        error_log('PHPExcel Error: ' . $e->getMessage());
    }
    
    return $groups;
}

if ($_SERVER['REQUEST_METHOD'] == 'POST' && $t == "save") {
    $groups = isset($_POST['groups']) ? json_decode($_POST['groups'], true) : array();
    $ticket_date = mysqli_real_escape_string($conn, $_POST['ticket_date']);
    $ticket_time = mysqli_real_escape_string($conn, $_POST['ticket_time']);
    $priority = intval($_POST['priority']);
    $remarks = mysqli_real_escape_string($conn, $_POST['remarks']);

    $ticketTypeMap = array(
        '标准票' => 'MP2022070117025856157',
        '老人票' => 'MP2022070419504838714',
        '学生票' => 'MP2022070419411024189',
        '未成年' => 'MP2022070117104622099'
    );

    $idTypeMap = array(
        '身份证' => '0',
        '港澳台证件' => '1',
        '护照' => '2'
    );

    $successCount = 0;
    $failCount = 0;

    foreach ($groups as $group) {
        if (empty($group)) continue;

        $firstPerson = $group[0];
        $group_name = $firstPerson['name'];
        
        $randomSuffix = str_pad(rand(0, 99999999), 8, '0', STR_PAD_LEFT);
        $phone = '173' . $randomSuffix;
        
        $assigned_count = 0;

        $name1 = isset($group[0]) ? mysqli_real_escape_string($conn, $group[0]['name']) : '';
        $id_type1 = isset($group[0]) ? (isset($idTypeMap[$group[0]['id_type']]) ? $idTypeMap[$group[0]['id_type']] : '0') : '0';
        $id_num1 = isset($group[0]) ? mysqli_real_escape_string($conn, $group[0]['id_num']) : '';
        $modelcode1 = isset($group[0]) ? (isset($ticketTypeMap[$group[0]['ticket_name']]) ? $ticketTypeMap[$group[0]['ticket_name']] : '') : '';

        $name2 = isset($group[1]) ? mysqli_real_escape_string($conn, $group[1]['name']) : '';
        $id_type2 = isset($group[1]) ? (isset($idTypeMap[$group[1]['id_type']]) ? $idTypeMap[$group[1]['id_type']] : '0') : '0';
        $id_num2 = isset($group[1]) ? mysqli_real_escape_string($conn, $group[1]['id_num']) : '';
        $modelcode2 = isset($group[1]) ? (isset($ticketTypeMap[$group[1]['ticket_name']]) ? $ticketTypeMap[$group[1]['ticket_name']] : '') : '';

        $name3 = isset($group[2]) ? mysqli_real_escape_string($conn, $group[2]['name']) : '';
        $id_type3 = isset($group[2]) ? (isset($idTypeMap[$group[2]['id_type']]) ? $idTypeMap[$group[2]['id_type']] : '0') : '0';
        $id_num3 = isset($group[2]) ? mysqli_real_escape_string($conn, $group[2]['id_num']) : '';
        $modelcode3 = isset($group[2]) ? (isset($ticketTypeMap[$group[2]['ticket_name']]) ? $ticketTypeMap[$group[2]['ticket_name']] : '') : '';

        $name4 = isset($group[3]) ? mysqli_real_escape_string($conn, $group[3]['name']) : '';
        $id_type4 = isset($group[3]) ? (isset($idTypeMap[$group[3]['id_type']]) ? $idTypeMap[$group[3]['id_type']] : '0') : '0';
        $id_num4 = isset($group[3]) ? mysqli_real_escape_string($conn, $group[3]['id_num']) : '';
        $modelcode4 = isset($group[3]) ? (isset($ticketTypeMap[$group[3]['ticket_name']]) ? $ticketTypeMap[$group[3]['ticket_name']] : '') : '';

        $name5 = isset($group[4]) ? mysqli_real_escape_string($conn, $group[4]['name']) : '';
        $id_type5 = isset($group[4]) ? (isset($idTypeMap[$group[4]['id_type']]) ? $idTypeMap[$group[4]['id_type']] : '0') : '0';
        $id_num5 = isset($group[4]) ? mysqli_real_escape_string($conn, $group[4]['id_num']) : '';
        $modelcode5 = isset($group[4]) ? (isset($ticketTypeMap[$group[4]['ticket_name']]) ? $ticketTypeMap[$group[4]['ticket_name']] : '') : '';

        $sql = "INSERT INTO guests (group_name, phone, ticket_date, ticket_time, status, remarks, priority, order_wxid, assigned_count, name1, id_type1, id_num1, modelcode1, name2, id_type2, id_num2, modelcode2, name3, id_type3, id_num3, modelcode3, name4, id_type4, id_num4, modelcode4, name5, id_type5, id_num5, modelcode5) VALUES ('$group_name', '$phone', '$ticket_date', '$ticket_time', '0', '$remarks', '$priority', '', '$assigned_count', '$name1', '$id_type1', '$id_num1', '$modelcode1', '$name2', '$id_type2', '$id_num2', '$modelcode2', '$name3', '$id_type3', '$id_num3', '$modelcode3', '$name4', '$id_type4', '$id_num4', '$modelcode4', '$name5', '$id_type5', '$id_num5', '$modelcode5')";

        if (mysqli_query($conn, $sql)) {
            $successCount++;
        } else {
            $failCount++;
        }
    }

    header('Content-Type: application/json;charset=utf-8');
    echo json_encode(['code' => 0, 'msg' => "成功添加{$successCount}组，失败{$failCount}组"]);
    exit;
}
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>批量添加客人</title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
    <style>
        .group-preview {
            border: 1px solid #e2e2e2;
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 4px;
        }
        .group-title {
            font-weight: bold;
            margin-bottom: 10px;
            color: #1e9fff;
        }
        .group-title.warning {
            color: #ff5722;
        }
        .person-row {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            padding: 10px;
            background-color: #f9f9f9;
            border-radius: 4px;
        }
        .person-row.exceeded {
            text-decoration: line-through;
            color: #999;
            opacity: 0.6;
        }
        .person-row:last-child {
            margin-bottom: 0;
        }
        .person-index {
            width: 30px;
            font-weight: bold;
            color: #666;
        }
        .person-field {
            margin-right: 10px;
        }
        .person-field input,
        .person-field select {
            width: 100%;
        }
        .name-input {
            width: 100px;
        }
        .id-type-select {
            width: 120px;
        }
        .id-num-input {
            width: 190px;
        }
        .ticket-name-select {
            width: 100px;
        }
        .warning-icon {
            color: #ff5722;
            font-size: 16px;
            margin-left: 5px;
            cursor: pointer;
        }
        .readonly-input {
            background-color: #f5f7fa;
            color: #666;
        }
    </style>
</head>
<body>
<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-body">
            <form class="layui-form" lay-filter="batchGuestForm" action="" method="post">
                
                <div class="layui-form-item">
                    <label class="layui-form-label">导入Excel</label>
                    <div class="layui-input-inline">
                        <button type="button" class="layui-btn layui-btn-normal" id="uploadBtn">
                            <i class="layui-icon layui-icon-upload-drag"></i> 上传Excel
                        </button>
                        <input type="file" id="excelFile" accept=".xlsx,.xls" style="display: none;">
                        <span id="uploadStatus" style="margin-left: 10px; color: #999;"></span>
                    </div>
                </div>

                <div class="layui-form-item">
                    <label class="layui-form-label">客人组名</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <input type="text" name="group_name" id="group_name" lay-verify="required" value="系统生成" autocomplete="off" class="layui-input readonly-input" readonly>
                    </div>
                    <label class="layui-form-label">手机号</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <input type="text" name="phone" value="系统生成" autocomplete="off" class="layui-input readonly-input" readonly>
                    </div>
                </div>

                <div class="layui-form-item">
                    <label class="layui-form-label">购票日期</label>
                    <div class="layui-input-inline" style="width: 100px;">
                        <input type="text" name="ticket_date" id="ticket_date" lay-verify="required" placeholder="选择日期" autocomplete="off" class="layui-input">
                    </div>
                    <div class="layui-input-inline" style="width: 90px;">
                        <select name="ticket_time" lay-verify="required">
                            <option value="全天" selected>全天</option>
                            <option value="上午">上午</option>
                            <option value="下午">下午</option>
                        </select>
                    </div>
                </div>

                <div class="layui-form-item">
                    <label class="layui-form-label">优先级</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <select name="priority" lay-verify="required">
                            <option value="1" selected>1星</option>
                            <option value="2">2星</option>
                            <option value="3">3星</option>
                            <option value="4">4星</option>
                            <option value="5">5星</option>
                        </select>
                    </div>
                    <label class="layui-form-label">备注信息</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <input type="text" name="remarks" placeholder="请输入备注" autocomplete="off" class="layui-input">
                    </div>
                </div>

                <div class="layui-form-item">
                    <label class="layui-form-label">预览数据</label>
                    <div class="layui-input-block" id="previewArea">
                        <div style="color: #999; padding: 10px;">请先上传Excel文件</div>
                    </div>
                </div>

                <div class="layui-form-item">
                    <div class="layui-input-block">
                        <button class="layui-btn" lay-submit lay-filter="saveBtn" id="saveBtn" disabled>立即提交</button>
                        <button type="button" class="layui-btn layui-btn-primary" id="resetBtn">重置</button>
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
}).use(['form', 'layer', 'laydate', 'upload'], function(){
    var form = layui.form
    ,layer = layui.layer
    ,laydate = layui.laydate
    ,upload = layui.upload
    ,$ = layui.$;
    
    laydate.render({
        elem: '#ticket_date'
    });
    
    var groupsData = [];
    
    $('#uploadBtn').on('click', function(){
        $('#excelFile').click();
    });
    
    $('#excelFile').on('change', function(){
        var file = this.files[0];
        if (!file) return;
        
        $('#uploadStatus').text('上传中...');
        
        var formData = new FormData();
        formData.append('excel_file', file);
        
        layer.load(2);
        
        $.ajax({
            url: '?t=upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            dataType: 'json',
            success: function(res){
                layer.closeAll('loading');
                if (res.code === 0) {
                    groupsData = res.data;
                    renderPreview(groupsData);
                    $('#saveBtn').prop('disabled', false);
                    $('#uploadStatus').text('解析成功，共' + groupsData.length + '组');
                    layer.msg('解析成功，共' + groupsData.length + '组');
                } else {
                    $('#uploadStatus').text('解析失败');
                    layer.msg(res.msg, {icon: 2});
                    if (res.debug) {
                        console.log('Debug info:', res.debug);
                    }
                }
            },
            error: function(xhr, status, error){
                layer.closeAll('loading');
                $('#uploadStatus').text('上传失败');
                console.log('Upload error:', status, error);
                console.log('Response:', xhr.responseText);
                layer.msg('上传失败: ' + (xhr.responseText || error), {icon: 2});
            }
        });
        
        $(this).val('');
    });
    
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
    
    function checkTicketTypeMatch(ticketName, idType, idNum) {
        if (idType !== '身份证') {
            return { valid: true, reason: '' };
        }
        
        if (!idNum || idNum.length !== 18) {
            return { valid: true, reason: '' };
        }
        
        var age = getAgeFromIdCard(idNum);
        if (age === null) {
            return { valid: true, reason: '' };
        }
        
        var reason = '';
        var valid = true;
        
        if (ticketName === '老人票' && age < 60) {
            valid = false;
            reason = '年龄' + age + '岁，不符合老人票要求（60岁以上）';
        } else if (ticketName === '标准票' && age >= 60) {
            valid = false;
            reason = '年龄' + age + '岁，建议选择老人票';
        } else if (ticketName === '未成年' && age >= 18) {
            valid = false;
            reason = '年龄' + age + '岁，不符合未成年票要求（18岁以下）';
        } else if (ticketName === '学生票' && (age < 6 || age > 22)) {
            valid = false;
            reason = '年龄' + age + '岁，可能不符合学生票要求';
        }
        
        return { valid: valid, reason: reason };
    }
    
    function renderPreview(groups) {
        var html = '';
        
        groups.forEach(function(group, index){
            var isExceeded = group.length > 5;
            var titleClass = isExceeded ? 'group-title warning' : 'group-title';
            var titleText = isExceeded ? '第' + (index + 1) + '组（' + group.length + '人）- 超过5人，请检查！' : '第' + (index + 1) + '组（' + group.length + '人）';
            
            html += '<div class="group-preview" data-group-index="' + index + '">';
            html += '<div class="' + titleClass + '">' + titleText + '</div>';
            
            group.forEach(function(person, pIndex){
                var isOverLimit = pIndex >= 5;
                var rowClass = isOverLimit ? 'person-row exceeded' : 'person-row';
                
                var matchResult = checkTicketTypeMatch(person.ticket_name, person.id_type, person.id_num);
                var warningHtml = '';
                if (!matchResult.valid) {
                    warningHtml = '<i class="layui-icon layui-icon-tips warning-icon" title="' + matchResult.reason + '"></i>';
                }
                
                html += '<div class="' + rowClass + '" data-person-index="' + pIndex + '">';
                html += '<div class="person-index">' + (pIndex + 1) + '</div>';
                
                html += '<div class="person-field name-input">';
                html += '<input type="text" class="layui-input person-name" value="' + person.name + '" placeholder="姓名">';
                html += '</div>';
                
                html += '<div class="person-field id-type-select">';
                html += '<select class="layui-input id-type" lay-ignore>';
                html += '<option value="身份证" ' + (person.id_type === '身份证' ? 'selected' : '') + '>身份证</option>';
                html += '<option value="港澳台证件" ' + (person.id_type === '港澳台证件' ? 'selected' : '') + '>港澳居民来往内地通行证</option>';
                html += '<option value="护照" ' + (person.id_type === '护照' ? 'selected' : '') + '>护照</option>';
                html += '</select>';
                html += '</div>';
                
                html += '<div class="person-field id-num-input">';
                html += '<input type="text" class="layui-input id-num" value="' + person.id_num + '" placeholder="证件号码">';
                html += '</div>';
                
                html += '<div class="person-field ticket-name-select">';
                html += '<select class="layui-input ticket-name" lay-ignore>';
                html += '<option value="标准票" ' + (person.ticket_name === '标准票' ? 'selected' : '') + '>标准票</option>';
                html += '<option value="老人票" ' + (person.ticket_name === '老人票' ? 'selected' : '') + '>老人票</option>';
                html += '<option value="学生票" ' + (person.ticket_name === '学生票' ? 'selected' : '') + '>学生票</option>';
                html += '<option value="未成年" ' + (person.ticket_name === '未成年' ? 'selected' : '') + '>未成年</option>';
                html += '</select>';
                html += warningHtml;
                html += '</div>';
                
                html += '</div>';
            });
            
            html += '</div>';
        });
        
        $('#previewArea').html(html);
    }
    
    $('#resetBtn').on('click', function(){
        groupsData = [];
        $('#previewArea').html('<div style="color: #999; padding: 10px;">请先上传Excel文件</div>');
        $('#group_name').val('');
        $('#saveBtn').prop('disabled', true);
        $('#excelFile').val('');
    });
    
    form.on('submit(saveBtn)', function(data){
        if (groupsData.length === 0) {
            layer.msg('请先上传Excel文件', {icon: 2});
            return false;
        }
        
        var editedGroups = [];
        $('.group-preview').each(function(){
            var groupIndex = $(this).data('group-index');
            var group = [];
            var personCount = 0;
            
            $(this).find('.person-row').each(function(){
                if (personCount >= 5) {
                    return false;
                }
                
                var personIndex = $(this).data('person-index');
                var ticketName = $(this).find('.ticket-name').val();
                var name = $(this).find('.person-name').val();
                var idType = $(this).find('.id-type').val();
                var idNum = $(this).find('.id-num').val();
                
                if (name && name.trim() !== '') {
                    group.push({
                        ticket_name: ticketName,
                        name: name,
                        id_type: idType,
                        id_num: idNum
                    });
                    personCount++;
                }
            });
            
            if (group.length > 0) {
                editedGroups.push(group);
            }
        });
        
        if (editedGroups.length === 0) {
            layer.msg('没有有效的客人数据', {icon: 2});
            return false;
        }
        
        layer.load(2);
        
        $.ajax({
            url: '?t=save',
            type: 'POST',
            data: {
                groups: JSON.stringify(editedGroups),
                ticket_date: data.field.ticket_date,
                ticket_time: data.field.ticket_time,
                priority: data.field.priority,
                remarks: data.field.remarks
            },
            success: function(res){
                layer.closeAll('loading');
                if (res.code === 0) {
                    layer.msg(res.msg, {icon: 1}, function(){
                        parent.layer.closeAll();
                        parent.layui.table.reload('data-table');
                    });
                } else {
                    layer.msg(res.msg, {icon: 2});
                }
            },
            error: function(){
                layer.closeAll('loading');
                layer.msg('保存失败', {icon: 2});
            }
        });
        
        return false;
    });
    
    function updateAgeWarning(row) {
        var ticketName = row.find('.ticket-name').val();
        var idType = row.find('.id-type').val();
        var idNum = row.find('.id-num').val();
        var warningContainer = row.find('.id-num-input');
        
        warningContainer.find('.warning-text').remove();
        
        if (ticketName === '老人票' && idType === '身份证' && idNum && idNum.length === 18) {
            var birthYear = parseInt(idNum.substring(6, 10));
            var currentYear = new Date().getFullYear();
            var age = currentYear - birthYear;
            if (age < 60) {
                warningContainer.append('<span class="warning-text">（年龄' + age + '岁，请检查）</span>');
            }
        }
    }
    
    $(document).on('change', '.ticket-name, .id-type', function(){
        var row = $(this).closest('.person-row');
        updateAgeWarning(row);
    });
    
    $(document).on('input', '.id-num', function(){
        var row = $(this).closest('.person-row');
        updateAgeWarning(row);
    });
    
    form.render();
});
</script>
</body>
</html>
