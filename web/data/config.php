<?php
/**
 * EXHome 数据库配置文件
 * 包含数据库连接信息和系统设置
 */

// 防止直接访问
if (!defined('IN_EXHOME')) {
    define('IN_EXHOME', true);
}

// ========================================================
// 数据库配置
// ========================================================
$db_config = array(
    'host'     => 'localhost',      // 数据库地址
    'port'     => 3306,                // 数据库端口
    'username' => 'YOUR_MYSQL_USER',   // 数据库账号
    'password' => 'YOUR_MYSQL_PASSWORD', // 数据库密码
    'database' => 'YOUR_MYSQL_DB',     // 数据库名称
    'charset'  => 'utf8mb4',           // 字符集
    'prefix'   => '',                  // 表前缀
);

// ========================================================
// 系统基础配置
// ========================================================
$system_config = array(
    'app_name'    => 'EXHome',
    'app_version' => '1.0.0',
    'debug_mode'  => false,            // 调试模式
    'timezone'    => 'Asia/Shanghai',  // 时区
);

// ========================================================
// 分页配置
// ========================================================
$page_config = array(
    'default_size' => 10,              // 默认每页条数
    'max_size'     => 100,             // 最大每页条数
);

// ========================================================
// 订单状态配置
// ========================================================
$order_status = array(
    0 => array('text' => '待支付', 'color' => '#ff9800', 'class' => 'layui-btn-warm'),
    1 => array('text' => '待接单', 'color' => '#2196f3', 'class' => 'layui-btn-normal'),
    2 => array('text' => '已接单', 'color' => '#9c27b0', 'class' => 'layui-btn-purple'),
    3 => array('text' => '配送中', 'color' => '#00bcd4', 'class' => 'layui-btn-cyan'),
    4 => array('text' => '已完成', 'color' => '#4caf50', 'class' => 'layui-btn-success'),
    5 => array('text' => '已取消', 'color' => '#f44336', 'class' => 'layui-btn-danger'),
);

// ========================================================
// 订单类型配置
// ========================================================
$order_types = array(
    1 => array('text' => '帮我送', 'icon' => 'layui-icon-send'),
    2 => array('text' => '帮我取', 'icon' => 'layui-icon-suitcase'),
    3 => array('text' => '帮我买', 'icon' => 'layui-icon-cart'),
    4 => array('text' => '帮我做', 'icon' => 'layui-icon-service'),
);

// ========================================================
// 紧急程度配置
// ========================================================
$urgency_levels = array(
    1 => array('text' => '普通', 'color' => '#4caf50', 'fee' => 0),
    2 => array('text' => '加急', 'color' => '#ff9800', 'fee' => 5),
    3 => array('text' => '特急', 'color' => '#f44336', 'fee' => 10),
);

// ========================================================
// 支付方式配置
// ========================================================
$pay_types = array(
    0 => array('text' => '未支付', 'icon' => 'layui-icon-close'),
    1 => array('text' => '微信支付', 'icon' => 'layui-icon-wechat'),
    2 => array('text' => '支付宝支付', 'icon' => 'layui-icon-rmb'),
    9 => array('text' => '余额支付', 'icon' => 'layui-icon-rmb'),
);

// ========================================================
// 用户状态配置
// ========================================================
$user_status = array(
    0 => array('text' => '禁用', 'color' => '#f44336', 'class' => 'layui-btn-danger'),
    1 => array('text' => '正常', 'color' => '#4caf50', 'class' => 'layui-btn-success'),
);

// ========================================================
// 跑腿员认证状态配置
// ========================================================
$runner_status = array(
    0 => array('text' => '未认证', 'color' => '#9e9e9e', 'class' => 'layui-btn-disabled'),
    1 => array('text' => '审核中', 'color' => '#ff9800', 'class' => 'layui-btn-warm'),
    2 => array('text' => '已通过', 'color' => '#4caf50', 'class' => 'layui-btn-success'),
    3 => array('text' => '已拒绝', 'color' => '#f44336', 'class' => 'layui-btn-danger'),
);

// ========================================================
// 提现状态配置
// ========================================================
$withdraw_status = array(
    0 => array('text' => '待审核', 'color' => '#ff9800', 'class' => 'layui-btn-warm'),
    1 => array('text' => '审核通过', 'color' => '#2196f3', 'class' => 'layui-btn-normal'),
    2 => array('text' => '审核拒绝', 'color' => '#f44336', 'class' => 'layui-btn-danger'),
    3 => array('text' => '已打款', 'color' => '#4caf50', 'class' => 'layui-btn-success'),
);

// ========================================================
// 公告类型配置
// ========================================================
$notice_types = array(
    1 => array('text' => '平台公告', 'color' => '#2196f3'),
    2 => array('text' => '活动通知', 'color' => '#ff9800'),
    3 => array('text' => '系统通知', 'color' => '#9c27b0'),
);

// ========================================================
// 公告状态配置
// ========================================================
$notice_status = array(
    0 => array('text' => '草稿', 'color' => '#9e9e9e', 'class' => 'layui-btn-disabled'),
    1 => array('text' => '已发布', 'color' => '#4caf50', 'class' => 'layui-btn-success'),
    2 => array('text' => '已下架', 'color' => '#f44336', 'class' => 'layui-btn-danger'),
);

// ========================================================
// 钱包明细场景配置
// ========================================================
$wallet_scenes = array(
    1 => array('text' => '充值', 'type' => 'income', 'color' => '#4caf50'),
    2 => array('text' => '提现', 'type' => 'expense', 'color' => '#f44336'),
    3 => array('text' => '订单收入', 'type' => 'income', 'color' => '#4caf50'),
    4 => array('text' => '订单支出', 'type' => 'expense', 'color' => '#f44336'),
    5 => array('text' => '退款', 'type' => 'income', 'color' => '#2196f3'),
    6 => array('text' => '奖励', 'type' => 'income', 'color' => '#ff9800'),
);

// ========================================================
// 全局变量
// ========================================================
$conn = null;  // 数据库连接对象
$setting = array();  // 系统设置缓存

/**
 * 获取数据库连接
 * @return mysqli
 */
function getDbConnection() {
    global $conn, $db_config;
    
    if ($conn === null) {
        $conn = mysqli_connect(
            $db_config['host'],
            $db_config['username'],
            $db_config['password'],
            $db_config['database'],
            $db_config['port']
        );
        
        if (!$conn) {
            die('数据库连接失败: ' . mysqli_connect_error());
        }
        
        mysqli_set_charset($conn, $db_config['charset']);
    }
    
    return $conn;
}

/**
 * 获取系统设置
 * @param string $key 设置键名
 * @param mixed $default 默认值
 * @return mixed
 */
function getSetting($key = '', $default = '') {
    global $setting, $conn;
    
    // 如果设置未加载，从数据库加载
    if (empty($setting)) {
        $db = getDbConnection();
        $sql = "SELECT `key`, `value`, `type` FROM settings";
        $result = mysqli_query($db, $sql);
        
        while ($row = mysqli_fetch_assoc($result)) {
            if ($row['type'] == 'number') {
                $setting[$row['key']] = floatval($row['value']);
            } elseif ($row['type'] == 'json') {
                $setting[$row['key']] = json_decode($row['value'], true);
            } else {
                $setting[$row['key']] = $row['value'];
            }
        }
    }
    
    // 返回指定设置或全部设置
    if ($key === '') {
        return $setting;
    }
    
    return isset($setting[$key]) ? $setting[$key] : $default;
}

/**
 * 更新系统设置
 * @param string $key 设置键名
 * @param mixed $value 设置值
 * @return bool
 */
function updateSetting($key, $value) {
    global $setting, $conn;
    
    $db = getDbConnection();
    $value = mysqli_real_escape_string($db, $value);
    
    $sql = "UPDATE settings SET `value` = '{$value}' WHERE `key` = '{$key}'";
    $result = mysqli_query($db, $sql);
    
    if ($result) {
        $setting[$key] = $value;
    }
    
    return $result;
}

/**
 * 生成订单编号
 * @return string
 */
function generateOrderNo() {
    return date('YmdHis') . mt_rand(1000, 9999);
}

/**
 * 获取状态文本
 * @param array $config 状态配置数组
 * @param int $status 状态值
 * @return string
 */
function getStatusText($config, $status) {
    return isset($config[$status]) ? $config[$status]['text'] : '未知';
}

/**
 * 获取状态颜色
 * @param array $config 状态配置数组
 * @param int $status 状态值
 * @return string
 */
function getStatusColor($config, $status) {
    return isset($config[$status]) ? $config[$status]['color'] : '#999';
}

/**
 * 获取状态按钮样式
 * @param array $config 状态配置数组
 * @param int $status 状态值
 * @return string
 */
function getStatusClass($config, $status) {
    return isset($config[$status]) ? $config[$status]['class'] : '';
}

/**
 * 记录订单日志
 * @param int $order_id 订单ID
 * @param string $order_no 订单编号
 * @param int $status 订单状态
 * @param string $status_text 状态描述
 * @param int $operator_id 操作人ID
 * @param int $operator_type 操作人类型
 * @param string $operator_name 操作人名称
 * @param string $content 操作内容
 * @return bool
 */
function addOrderLog($order_id, $order_no, $status, $status_text, $operator_id = 0, $operator_type = 3, $operator_name = '系统', $content = '') {
    $db = getDbConnection();
    
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    
    $sql = "INSERT INTO order_logs (order_id, order_no, status, status_text, operator_id, operator_type, operator_name, content, ip, create_time) 
            VALUES ({$order_id}, '{$order_no}', {$status}, '{$status_text}', {$operator_id}, {$operator_type}, '{$operator_name}', '{$content}', '{$ip}', NOW())";
    
    return mysqli_query($db, $sql);
}

/**
 * 记录钱包明细
 * @param int $user_id 用户ID
 * @param int $type 类型(1=收入,2=支出)
 * @param float $amount 金额
 * @param float $balance 变动后余额
 * @param int $scene 场景
 * @param int $order_id 关联订单ID
 * @param string $order_no 关联订单号
 * @param string $title 标题
 * @param string $remark 备注
 * @return bool
 */
function addWalletLog($user_id, $type, $amount, $balance, $scene, $order_id = 0, $order_no = '', $title = '', $remark = '') {
    $db = getDbConnection();
    
    $sql = "INSERT INTO wallet_logs (user_id, type, amount, balance, scene, order_id, order_no, title, remark, create_time) 
            VALUES ({$user_id}, {$type}, {$amount}, {$balance}, {$scene}, {$order_id}, '{$order_no}', '{$title}', '{$remark}', NOW())";
    
    return mysqli_query($db, $sql);
}

/**
 * 安全过滤
 * @param string $str 输入字符串
 * @return string
 */
function filterInput($str) {
    $str = trim($str);
    $str = htmlspecialchars($str, ENT_QUOTES, 'UTF-8');
    return $str;
}

/**
 * 获取分页参数
 * @return array
 */
function getPageParams() {
    global $page_config;
    
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : $page_config['default_size'];
    
    if ($page < 1) $page = 1;
    if ($limit < 1) $limit = $page_config['default_size'];
    if ($limit > $page_config['max_size']) $limit = $page_config['max_size'];
    
    $offset = ($page - 1) * $limit;
    
    return array(
        'page'   => $page,
        'limit'  => $limit,
        'offset' => $offset
    );
}

/**
 * 生成分页HTML
 * @param int $total 总记录数
 * @param int $page 当前页
 * @param int $limit 每页条数
 * @param string $url 基础URL
 * @return string
 */
function generatePagination($total, $page, $limit, $url = '') {
    $totalPages = ceil($total / $limit);
    if ($totalPages <= 1) return '';
    
    $html = '<div class="layui-box layui-laypage layui-laypage-default">';
    
    // 上一页
    if ($page > 1) {
        $html .= '<a href="' . $url . '&page=' . ($page - 1) . '" class="layui-laypage-prev">上一页</a>';
    } else {
        $html .= '<span class="layui-laypage-prev layui-disabled">上一页</span>';
    }
    
    // 页码
    $start = max(1, $page - 2);
    $end = min($totalPages, $page + 2);
    
    if ($start > 1) {
        $html .= '<a href="' . $url . '&page=1">1</a>';
        if ($start > 2) $html .= '<span class="layui-laypage-spr">…</span>';
    }
    
    for ($i = $start; $i <= $end; $i++) {
        if ($i == $page) {
            $html .= '<span class="layui-laypage-curr"><em class="layui-laypage-em"></em><em>' . $i . '</em></span>';
        } else {
            $html .= '<a href="' . $url . '&page=' . $i . '">' . $i . '</a>';
        }
    }
    
    if ($end < $totalPages) {
        if ($end < $totalPages - 1) $html .= '<span class="layui-laypage-spr">…</span>';
        $html .= '<a href="' . $url . '&page=' . $totalPages . '">' . $totalPages . '</a>';
    }
    
    // 下一页
    if ($page < $totalPages) {
        $html .= '<a href="' . $url . '&page=' . ($page + 1) . '" class="layui-laypage-next">下一页</a>';
    } else {
        $html .= '<span class="layui-laypage-next layui-disabled">下一页</span>';
    }
    
    $html .= '</div>';
    
    return $html;
}

/**
 * 返回JSON响应
 * @param int $code 状态码
 * @param string $msg 消息
 * @param array $data 数据
 */
function jsonResponse($code, $msg = '', $data = array()) {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(array(
        'code' => $code,
        'msg'  => $msg,
        'data' => $data
    ));
    exit;
}

/**
 * 检查管理员登录状态
 * @return bool
 */
function checkAdminLogin() {
    if (!isset($_SESSION['admin_id']) || empty($_SESSION['admin_id'])) {
        // 检查记住登录的cookie
        if (isset($_COOKIE['admin_remember'])) {
            $cookie_value = base64_decode($_COOKIE['admin_remember']);
            $cookie_data = unserialize(DecryptStr($cookie_value));
            
            if ($cookie_data && isset($cookie_data['user_id'])) {
                $db = getDbConnection();
                $sql = "SELECT * FROM admin WHERE id = " . intval($cookie_data['user_id']) . " AND status = 1";
                $result = mysqli_query($db, $sql);
                $admin = mysqli_fetch_assoc($result);
                
                if ($admin) {
                    $_SESSION['admin_id'] = $admin['id'];
                    $_SESSION['username'] = $admin['username'];
                    $_SESSION['power'] = $admin['power'];
                    $_SESSION['admin_username'] = $admin['name'];
                    return true;
                }
            }
        }
        return false;
    }
    return true;
}

/**
 * 获取当前管理员信息
 * @return array|null
 */
function getCurrentAdmin() {
    if (!checkAdminLogin()) return null;
    
    return array(
        'id'       => $_SESSION['admin_id'],
        'username' => $_SESSION['username'],
        'power'    => $_SESSION['power'],
        'name'     => $_SESSION['admin_username']
    );
}

/**
 * 加密字符串
 * @param string $str 要加密的字符串
 * @return string
 */
if (!function_exists('EncryptStr')) {
    function EncryptStr($str) {
        $key = 'exhome2025';
        $str = base64_encode($str);
        $len = strlen($key);
        $code = '';
        for ($i = 0; $i < strlen($str); $i++) {
            $k = $i % $len;
            $code .= $str[$i] ^ $key[$k];
        }
        return base64_encode($code);
    }
}

/**
 * 解密字符串
 * @param string $str 要解密的字符串
 * @return string
 */
if (!function_exists('DecryptStr')) {
    function DecryptStr($str) {
        $key = 'exhome2025';
        $str = base64_decode($str);
        $len = strlen($key);
        $code = '';
        for ($i = 0; $i < strlen($str); $i++) {
            $k = $i % $len;
            $code .= $str[$i] ^ $key[$k];
        }
        return base64_decode($code);
    }
}
