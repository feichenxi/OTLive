<?php
header('Content-Type: application/json;charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, token');

require_once("../data/class.php");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

$conn = isset($_ENV['conn']) ? $_ENV['conn'] : null;

if (!$conn) {
    echo json_encode(['code' => 500, 'msg' => '数据库连接失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

$action = isset($_GET['action']) ? trim($_GET['action']) : '';

if ($action === 'get') {
    $room = isset($_GET['room']) ? trim($_GET['room']) : '';
    $license_id = isset($_GET['license_id']) ? intval($_GET['license_id']) : 0;
    
    if (!$room) {
        echo json_encode(['code' => 400, 'msg' => '房间参数错误'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    
    $room = mysqli_real_escape_string($conn, $room);
    $license_id = intval($license_id);
    
    $sql = "SELECT * FROM voice WHERE room = '$room' AND license_id = '$license_id' LIMIT 1";
    $result = mysqli_query($conn, $sql);
    
    if ($result && mysqli_num_rows($result) > 0) {
        $row = mysqli_fetch_assoc($result);
        echo json_encode([
            'code' => 0,
            'msg' => '获取成功',
            'data' => $row
        ], JSON_UNESCAPED_UNICODE);
    } else {
        echo json_encode([
            'code' => 0,
            'msg' => '暂无数据',
            'data' => null
        ], JSON_UNESCAPED_UNICODE);
    }
    exit;
}

if ($action === 'upload') {
    $room = isset($_POST['room']) ? trim($_POST['room']) : '';
    $license_id = isset($_POST['license_id']) ? intval($_POST['license_id']) : 0;
    $voice_text = isset($_POST['voice_text']) ? trim($_POST['voice_text']) : '';
    $ai_prompt = isset($_POST['ai_prompt']) ? trim($_POST['ai_prompt']) : '';
    
    if (!$room) {
        echo json_encode(['code' => 400, 'msg' => '房间参数错误'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    
    if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
        echo json_encode(['code' => 400, 'msg' => '文件上传失败'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    
    $file = $_FILES['file'];
    $allowedTypes = ['audio/wav', 'audio/x-wav', 'audio/mpeg', 'audio/mp3', 'audio/flac'];
    $fileExt = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    $allowedExts = ['wav', 'mp3', 'flac'];
    
    if (!in_array($fileExt, $allowedExts)) {
        echo json_encode(['code' => 400, 'msg' => '只支持WAV、MP3、FLAC格式文件'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    
    if ($file['size'] > 10 * 1024 * 1024) {
        echo json_encode(['code' => 400, 'msg' => '文件大小不能超过10MB'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    
    $uploadDir = $_SERVER['DOCUMENT_ROOT'] . '/uploads/voice/';
    if (!is_dir($uploadDir)) {
        mkdir($uploadDir, 0755, true);
    }
    
    $newFilename = $room . '_' . date('YmdHis') . '_' . uniqid() . '.' . $fileExt;
    $uploadPath = $uploadDir . $newFilename;
    
    if (!move_uploaded_file($file['tmp_name'], $uploadPath)) {
        echo json_encode(['code' => 500, 'msg' => '文件保存失败'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    
    $voiceSampleUrl = 'https://live.hzjt.com/uploads/voice/' . $newFilename;
    
    $room = mysqli_real_escape_string($conn, $room);
    $voice_text = mysqli_real_escape_string($conn, $voice_text);
    $ai_prompt = mysqli_real_escape_string($conn, $ai_prompt);
    
    $checkSql = "SELECT id FROM voice WHERE room = '$room' AND license_id = '$license_id' LIMIT 1";
    $checkResult = mysqli_query($conn, $checkSql);
    
    if ($checkResult && mysqli_num_rows($checkResult) > 0) {
        $updateSql = "UPDATE voice SET 
            voice_sample = '$newFilename', 
            voice_sample_url = '$voiceSampleUrl', 
            voice_text = '$voice_text', 
            ai_prompt = '$ai_prompt', 
            updated_at = NOW() 
            WHERE room = '$room' AND license_id = '$license_id'";
        
        if (mysqli_query($conn, $updateSql)) {
            echo json_encode([
                'code' => 0,
                'msg' => '上传成功',
                'data' => [
                    'id' => mysqli_fetch_assoc($checkResult)['id'],
                    'voice_sample' => $newFilename,
                    'voice_sample_url' => $voiceSampleUrl
                ]
            ], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 500, 'msg' => '数据库更新失败'], JSON_UNESCAPED_UNICODE);
        }
    } else {
        $insertSql = "INSERT INTO voice (room, license_id, voice_sample, voice_sample_url, voice_text, ai_prompt, voice_status) 
            VALUES ('$room', '$license_id', '$newFilename', '$voiceSampleUrl', '$voice_text', '$ai_prompt', 0)";
        
        if (mysqli_query($conn, $insertSql)) {
            echo json_encode([
                'code' => 0,
                'msg' => '上传成功',
                'data' => [
                    'id' => mysqli_insert_id($conn),
                    'voice_sample' => $newFilename,
                    'voice_sample_url' => $voiceSampleUrl
                ]
            ], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 500, 'msg' => '数据库插入失败'], JSON_UNESCAPED_UNICODE);
        }
    }
    exit;
}

if ($action === 'update_voice_id') {
    $input = json_decode(file_get_contents('php://input'), true);
    
    $room = isset($input['room']) ? trim($input['room']) : '';
    $license_id = isset($input['license_id']) ? intval($input['license_id']) : 0;
    $voice_id = isset($input['voice_id']) ? trim($input['voice_id']) : '';
    $voice_status = isset($input['voice_status']) ? intval($input['voice_status']) : 2;
    $voice_error = isset($input['voice_error']) ? trim($input['voice_error']) : '';
    
    if (!$room) {
        echo json_encode(['code' => 400, 'msg' => '房间参数错误'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    
    $room = mysqli_real_escape_string($conn, $room);
    $license_id = intval($license_id);
    $voice_id = mysqli_real_escape_string($conn, $voice_id);
    $voice_error = mysqli_real_escape_string($conn, $voice_error);
    
    $updateSql = "UPDATE voice SET 
        voice_id = " . ($voice_id ? "'$voice_id'" : "NULL") . ", 
        voice_status = '$voice_status', 
        voice_error = " . ($voice_error ? "'$voice_error'" : "NULL") . ", 
        updated_at = NOW() 
        WHERE room = '$room' AND license_id = '$license_id'";
    
    if (mysqli_query($conn, $updateSql)) {
        echo json_encode(['code' => 0, 'msg' => '更新成功'], JSON_UNESCAPED_UNICODE);
    } else {
        echo json_encode(['code' => 500, 'msg' => '数据库更新失败'], JSON_UNESCAPED_UNICODE);
    }
    exit;
}

if ($action === 'update_ai_prompt') {
    $input = json_decode(file_get_contents('php://input'), true);

    $room = isset($input['room']) ? trim($input['room']) : '';
    $license_id = isset($input['license_id']) ? intval($input['license_id']) : 0;
    $ai_prompt = isset($input['ai_prompt']) ? trim($input['ai_prompt']) : '';
    $voice_text = isset($input['voice_text']) ? trim($input['voice_text']) : '';
    $thank_value = isset($input['thank_value']) ? floatval($input['thank_value']) : 0;

    if (!$room) {
        echo json_encode(['code' => 400, 'msg' => '房间参数错误'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    if ($thank_value < 0 || $thank_value > 99999) {
        echo json_encode(['code' => 400, 'msg' => '答谢价值不能小于0或大于99999'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $room = mysqli_real_escape_string($conn, $room);
    $license_id = intval($license_id);
    $ai_prompt = mysqli_real_escape_string($conn, $ai_prompt);
    $voice_text = mysqli_real_escape_string($conn, $voice_text);

    $checkSql = "SELECT id FROM voice WHERE room = '$room' AND license_id = '$license_id' LIMIT 1";
    $checkResult = mysqli_query($conn, $checkSql);

    if ($checkResult && mysqli_num_rows($checkResult) > 0) {
        $updateSql = "UPDATE voice SET ai_prompt = '$ai_prompt', voice_text = '$voice_text', thank_value = '$thank_value', updated_at = NOW() WHERE room = '$room' AND license_id = '$license_id'";
        if (mysqli_query($conn, $updateSql)) {
            echo json_encode(['code' => 0, 'msg' => '更新成功'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 500, 'msg' => '数据库更新失败'], JSON_UNESCAPED_UNICODE);
        }
    } else {
        $insertSql = "INSERT INTO voice (room, license_id, ai_prompt, voice_text, thank_value, voice_status) VALUES ('$room', '$license_id', '$ai_prompt', '$voice_text', '$thank_value', 0)";
        if (mysqli_query($conn, $insertSql)) {
            echo json_encode(['code' => 0, 'msg' => '创建成功'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 500, 'msg' => '数据库插入失败'], JSON_UNESCAPED_UNICODE);
        }
    }
    exit;
}

if ($action === 'update_ai_thank') {
    $input = json_decode(file_get_contents('php://input'), true);

    $room = isset($input['room']) ? trim($input['room']) : '';
    $license_id = isset($input['license_id']) ? intval($input['license_id']) : 0;
    $ai_thank_enabled = isset($input['ai_thank_enabled']) ? intval($input['ai_thank_enabled']) : 0;

    if (!$room) {
        echo json_encode(['code' => 400, 'msg' => '房间参数错误'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $room = mysqli_real_escape_string($conn, $room);
    $license_id = intval($license_id);

    $checkSql = "SELECT id FROM voice WHERE room = '$room' AND license_id = '$license_id' LIMIT 1";
    $checkResult = mysqli_query($conn, $checkSql);

    if ($checkResult && mysqli_num_rows($checkResult) > 0) {
        $updateSql = "UPDATE voice SET ai_thank_enabled = '$ai_thank_enabled', updated_at = NOW() WHERE room = '$room' AND license_id = '$license_id'";
        if (mysqli_query($conn, $updateSql)) {
            echo json_encode(['code' => 0, 'msg' => '更新成功'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 500, 'msg' => '数据库更新失败'], JSON_UNESCAPED_UNICODE);
        }
    } else {
        $insertSql = "INSERT INTO voice (room, license_id, ai_thank_enabled, voice_status) VALUES ('$room', '$license_id', '$ai_thank_enabled', 0)";
        if (mysqli_query($conn, $insertSql)) {
            echo json_encode(['code' => 0, 'msg' => '创建成功'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 500, 'msg' => '数据库插入失败'], JSON_UNESCAPED_UNICODE);
        }
    }
    exit;
}

echo json_encode(['code' => 404, 'msg' => '接口不存在'], JSON_UNESCAPED_UNICODE);
