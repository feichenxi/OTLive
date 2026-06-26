<?php
session_start();

function conn(){
    $conn=mysqli_connect('localhost','YOUR_MYSQL_USER','YOUR_MYSQL_PASSWORD','YOUR_MYSQL_DB');
    // Check connection
    if (!$conn) {
        error_log("Database connection failed: " . mysqli_connect_error());
        // 返回null而不是继续执行
        return null;
    }
    return $conn;
}
$conn=conn();
if ($conn === null) {
    // 数据库连接失败，显示错误信息
    if (!isset($login) || $login !== "no") {
        die("数据库连接失败，请检查数据库配置或联系管理员。");
    }
}
$_ENV['conn']=$conn;

/*~~~~~~~~~~0核心配置~~~~~~~~~~*/
	/*全局配置*/
	
	// 从新的 settings 表加载配置
	$setting = array();
	if ($conn) {
		$sql = "SELECT `key`, `value`, `type` FROM settings";
		$result = mysqli_query($conn, $sql);
		if ($result) {
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
	}
	
	$_ENV['sms_dxmb']=$setting['sms_dxmb'] ?? '';
	$_ENV['sms_dxqm']=$setting['sms_dxqm'] ?? '';
	$_ENV['sms_KeyId']=$setting['sms_KeyId'] ?? '';
	$_ENV['sms_KeySecret']=$setting['sms_KeySecret'] ?? '';
	
	/*AI模型平台配置 - 三个核心参数*/
	$_ENV['ai_api_url'] = $setting['ai_api_url'] ?? '';
	$_ENV['ai_api_key'] = $setting['ai_api_key'] ?? '';
	$_ENV['ai_model'] = $setting['ai_model'] ?? '';

	/*****************验证登录模块*****************/
	// 完善权限验证机制：除访问api文件夹和index以外所有php页均需要验证是否登录
	$current_script = basename($_SERVER['SCRIPT_NAME']);
	$current_dir = basename(dirname($_SERVER['SCRIPT_NAME']));
	
	// 不需要登录验证的页面
	$no_login_required = array('login.php');
	$no_login_dirs = array('api', 'auto');
	
	// 检查是否需要登录验证
	$need_login_check = true;
	
	// 如果是不需要登录验证的页面
	if (in_array($current_script, $no_login_required)) {
		$need_login_check = false;
	}
	
	// 如果路径包含api目录或auto目录（包括子目录）
	$request_uri = $_SERVER['REQUEST_URI'];
	if (strpos($request_uri, '/api/') !== false || strpos($request_uri, '/auto/') !== false) {
		$need_login_check = false;
	}
	
	// 执行登录验证
	if ($need_login_check) {
		$admin_id = $_SESSION['admin_id'];
		
		// 如果SESSION中没有admin_id，则检查COOKIE
		if (empty($admin_id) && isset($_COOKIE['admin_remember'])) {
			// 解析COOKIE数据
			$cookie_data = unserialize(DecryptStr(base64_decode($_COOKIE['admin_remember'])));
			
			// 检查COOKIE是否有效（30天内）
			if (is_array($cookie_data) && isset($cookie_data['user_id']) && isset($cookie_data['login_time'])) {
				$user_id = $cookie_data['user_id'];
				$login_time = $cookie_data['login_time'];
				
				// 检查COOKIE是否在30天有效期内
				if ((time() - $login_time) < (30 * 24 * 60 * 60)) {
					// 查询用户信息
					$sql = "SELECT * FROM admin WHERE id='$user_id' limit 1";
					$result = mysqli_query($conn, $sql);
					$row = mysqli_fetch_array($result);
					
					if ($row['id']) {
						// 重新设置SESSION
						$_SESSION['admin_id'] = $row['id'];
						if($row['username']=='admin') {
							$_SESSION['store_id']=1;
						} else {
							$_SESSION['store_id']=$row['id'];
						}
						
						$_ENV['login_id'] = $row['id'];
						$_SESSION['username'] = $row['username'];
						$_SESSION['power'] = $row['power'];
						$_SESSION['admin_username'] = $row['name'];
						
						$admin_id = $row['id'];
						$admin_username = $row['username'];
					}
				} else {
					// COOKIE已过期，删除它
					setcookie('admin_remember', '', time() - 3600, '/', '', false, true);
				}
			}
		}
		
		if ($admin_id > 0) {
			$sql = "SELECT * FROM admin WHERE id='$admin_id' limit 1";
			$result = mysqli_query($conn, $sql);
			$row = mysqli_fetch_array($result);
			$admin_username = $row['username'];
		}

		if ($admin_id == 0 and $login != "no") {
			print '<script>window.location="/login.php";</script>';
			exit;
		}
	}
	/*****************验证登录模块*****************/
	
	/*接收通用*/
	@$t=$_GET['t'];
	@$s_t=$_GET['s_t'];
	/*接收通用*/
/*~~~~~~~~~~0核心配置~~~~~~~~~~*/


function Table_Info($table,$value="alldata",$where="1",$order="",$limit="")
{
	$conn=$_ENV['conn'];
	if ($conn === null) {
		// 数据库连接失败，返回空值
		if ($value=="alldata"){return array();}else{return '';}
	}
	if ($value=="alldata"){return mysqli_fetch_array(mysqli_query($conn,"select * from $table where $where $order $limit"));}else{return mysqli_fetch_array(mysqli_query($conn,"select $value from $table where $where $order $limit"))[$value];}
	
}


/**
 * 简单的对称加密函数（适用于小项目）
 * 使用异或和位移操作，不依赖额外库
 */
function EncryptStr($data, $key = 'hzkjjt_key_112233') {
    // 将密钥转换为字符串并计算其长度
    $keyStr = (string)$key;
    $keyLength = strlen($keyStr);
    
    // 转换数据为字符串
    $data = (string)$data;
    $dataLength = strlen($data);
    
    $encrypted = '';
    
    // 对每个字符进行加密
    for ($i = 0; $i < $dataLength; $i++) {
        // 使用密钥的不同位置字符进行异或
        $keyChar = $keyStr[$i % $keyLength];
        $encryptedChar = chr(ord($data[$i]) ^ ord($keyChar) ^ ($i % 256));
        $encrypted .= $encryptedChar;
    }
    
    return $encrypted;
}

/**
 * 简单的对称解密函数（适用于小项目）
 * 使用异或和位移操作，不依赖额外库
 */
function DecryptStr($encryptedData, $key = 'hzkjjt_key_112233') {
    // 将密钥转换为字符串并计算其长度
    $keyStr = (string)$key;
    $keyLength = strlen($keyStr);
    $dataLength = strlen($encryptedData);
    
    $decrypted = '';
    
    // 对每个字符进行解密
    for ($i = 0; $i < $dataLength; $i++) {
        // 使用密钥的不同位置字符进行异或
        $keyChar = $keyStr[$i % $keyLength];
        $decryptedChar = chr(ord($encryptedData[$i]) ^ ord($keyChar) ^ ($i % 256));
        $decrypted .= $decryptedChar;
    }
    
    return $decrypted;
}

/**
 * 验证请求token
 */
function validateToken() {
    // 获取token参数
    $encryptedToken = isset($_POST['_token']) ? $_POST['_token'] : '';
    
    // 如果没有token，返回false
    if (empty($encryptedToken)) {
        return false;
    }
    
    // 解密token
    $decryptedToken = DecryptStr($encryptedToken);
    
    // 检查解密是否成功
    if (empty($decryptedToken)) {
        return false;
    }
    
    // 转换为整数时间戳
    $tokenTimestamp = intval($decryptedToken);
    
    // 获取当前服务器时间戳
    $currentTimestamp = time() * 1000; // PHP time()返回秒，转换为毫秒以匹配前端
    
    // 计算时间差
    $timeDiff = abs($currentTimestamp - $tokenTimestamp);
    
    // 检查是否在允许的时间范围内
    return $timeDiff <= (TOKEN_TIMEOUT * 1000); // 转换为毫秒
}


/*时间戳转日期*/
function Time_Date($timestamp,$format='Y-m-d H:i:s')
{
    $date=date($format,$timestamp);
    return $date;
}
/*时间戳转日期*/

function Time_Date_short($timestamp,$format='Y-m-d H:i:s')
{
    $date=date($format,$timestamp);
    if (substr($date,0,4)==date("Y")){$date=substr($date,5,-3);}else{{$date=substr($date,2,-3);}}
    return $date;
}
/*时间戳转日期*/


/*去除HTML*/
function Del_Html($str)
{
	/*多个br换*/$str=preg_replace('/(\s*<br[^>]*>){1,}/','', $str);$str=str_replace(array("<br>"),array("\n"),$str);
	/*去除HTML*/$str=strip_tags($str,"<br><b><p><img><strong><u><i><s>");
	/*全文转义*/$str=addslashes($str);
	$str=trim($str);
	return $str;
}


/*财务增减*/
function FJJ($uid,$type,$amount,$remarks,$class=0)
{
	$conn=conn();
	$latestBalance=Table_Info("financial_details", "balance", "uid='$uid'", "order by id desc", "limit 1");
	if ($latestBalance>=0){$balance=$latestBalance+$amount;}else{$balance=$amount;}
	if ($amount!=0)
	{
		$sql="INSERT INTO financial_details (uid,type,amount,balance,remarks,class) VALUES ('$uid','$type','$amount','$balance','$remarks','$class')";
		$que=mysqli_query($conn,$sql);
		$ftid=mysqli_insert_id($conn);
	}
	return $latestBalance;
}
/*财务增减*/