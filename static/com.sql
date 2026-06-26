-- phpMyAdmin SQL Dump
-- version 5.1.1
-- https://www.phpmyadmin.net/
--
-- 主机： localhost
-- 生成日期： 2026-03-05 22:58:59
-- 服务器版本： 5.7.44-log
-- PHP 版本： 7.3.32

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- 数据库： `live`
--

-- --------------------------------------------------------

--
-- 表的结构 `com`
--

CREATE TABLE `com` (
  `id` int(10) NOT NULL COMMENT '主键ID',
  `type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT '命令类型',
  `room` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT '房间IP',
  `license_id` int(11) DEFAULT NULL COMMENT '授权ID',
  `command` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT '命令',
  `status` tinyint(4) DEFAULT '0' COMMENT '状态: -1失败 0等待 1成功',
  `at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='命令表';

--
-- 转存表中的数据 `com`
--

INSERT INTO `com` (`id`, `type`, `room`, `command`, `status`, `at`) VALUES
(2, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 01:14:15'),
(3, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 12:03:55'),
(4, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 12:10:40'),
(5, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 12:21:18'),
(6, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 12:29:21'),
(7, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 12:37:07'),
(8, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 12:50:12'),
(9, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 12:56:15'),
(10, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 13:03:29'),
(11, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 13:10:32'),
(12, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 13:31:30'),
(13, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 13:36:03'),
(14, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 13:42:36'),
(15, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 13:53:13'),
(16, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 13:54:39'),
(17, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 14:05:34'),
(18, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 14:16:40'),
(19, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 14:19:02'),
(20, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 14:33:08'),
(21, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 14:46:39'),
(22, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:02:50'),
(23, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:04:05'),
(24, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:04:48'),
(25, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:05:10'),
(26, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:05:24'),
(27, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:18:26'),
(28, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 15:23:48'),
(29, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:25:02'),
(30, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:26:45'),
(31, 'stop_monitor', '192.168.1.102', '', -1, '2026-02-15 15:26:45'),
(32, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:26:46'),
(33, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 15:41:31'),
(34, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:22:33'),
(35, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:39:58'),
(36, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:43:56'),
(37, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:45:01'),
(38, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:45:40'),
(39, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:47:29'),
(40, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:53:45'),
(41, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:54:39'),
(42, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 17:59:04'),
(43, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 18:44:09'),
(44, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 18:49:14'),
(45, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 18:50:40'),
(46, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 19:00:42'),
(47, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 19:23:29'),
(48, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 19:24:19'),
(49, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 19:32:19'),
(50, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 19:32:58'),
(51, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 21:21:20'),
(52, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 22:11:05'),
(53, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-15 22:15:56'),
(54, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 22:16:10'),
(55, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 22:20:25'),
(56, 'stop_monitor', '192.168.1.102', '', -1, '2026-02-15 22:20:59'),
(57, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 22:21:55'),
(58, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 22:22:45'),
(59, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-15 22:41:32'),
(60, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 22:49:38'),
(61, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 22:50:50'),
(62, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 22:55:19'),
(63, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 22:56:01'),
(64, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 22:57:25'),
(65, 'stop_monitor', '192.168.1.102', '', -1, '2026-02-15 23:13:29'),
(66, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 23:13:41'),
(67, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-15 23:14:07'),
(68, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 23:18:12'),
(69, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-15 23:19:10'),
(70, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 23:19:30'),
(71, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 23:20:52'),
(72, 'stop_monitor', '192.168.1.102', '', -1, '2026-02-15 23:22:24'),
(73, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', -1, '2026-02-15 23:22:36'),
(74, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 23:42:22'),
(75, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-15 23:57:27'),
(76, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-15 23:58:10'),
(77, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-16 00:00:32'),
(78, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-16 00:01:06'),
(79, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-16 00:02:10'),
(80, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/KJUg98PF', 1, '2026-02-16 14:11:41'),
(81, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/JeAQxTc9', 1, '2026-02-16 14:13:56'),
(82, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/JeAQxTc9', 1, '2026-02-18 00:48:35'),
(83, 'stop_monitor', '192.168.1.102', '', 1, '2026-02-18 00:48:41'),
(84, 'monitor', '192.168.1.102', 'https://v.kuaishou.com/JGvhw5eI', 1, '2026-02-19 11:13:30');

--
-- 转储表的索引
--

--
-- 表的索引 `com`
--
ALTER TABLE `com`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_status` (`status`),
  ADD KEY `idx_at` (`at`),
  ADD KEY `idx_license_room` (`license_id`, `room`, `status`);

--
-- 在导出的表使用AUTO_INCREMENT
--

--
-- 使用表AUTO_INCREMENT `com`
--
ALTER TABLE `com`
  MODIFY `id` int(10) NOT NULL AUTO_INCREMENT COMMENT '主键ID', AUTO_INCREMENT=85;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
