# PHPExcel
  是用来操作Office Excel 文档的一个PHP类库，它基于微软的OpenXML标准和PHP语言。可以使用它来读取、写入不同格式的电子表格

## 概述
  PHPExcel 是用来操作Office Excel 文档的一个PHP类库，它基于微软的OpenXML标准和PHP语言。可以使用它来读取、写入不同格式的电子表格，如 Excel (BIFF) .xls, Excel 2007 (OfficeOpenXML) .xlsx, CSV, Libre/OpenOffice Calc .ods, Gnumeric, PDF, HTML等等。

## 支持的格式

### 读取
* BIFF 5-8 (.xls) Excel 95 版本及以上[1] 
* Office Open XML (.xlsx) Excel 2007 版本及以上
* SpreadsheetML (.xml) Excel 2003
* Open Document Format/OASIS (.ods)
* Gnumeric
* HTML
* SYLK
* CSV

### 写入
* BIFF 8 (.xls) Excel 95 版本及以上
* Office Open XML (.xlsx) Excel 2007 版本及以上
* HTML
* CSV
* PDF (使用 tcPDF, DomPDF or mPDF PHP类库, 需要单独安装)

### 要求
* PHP 5.2.0 版本及以上
* PHP extension php_zip 开启 (如果你需要使用 PHPExcel 来操作 .xlsx .ods or .gnumeric 文件)
* PHP extension php_xml 开启
* PHP extension php_gd2 开启(选填, 如果需要计算准确的列宽需要开启此扩展)

## PHP读取示例代码编辑
> //获取上传的excel临时文件
> $path = $_FILES["file"]["tmp_name"];
> //将临时文件移动当前目录，可自定义存储位置
>  
> move_uploaded_file($_FILES["file"]["tmp_name"],$_FILES["file"]["name"]);
> //将获取在服务器中的Excel文件，此处为上传文件名
> $path = $_FILES["file"]["name"];
> //调用readExcel函数返回一个二维数组
> $exceArray = readExcel($path);
>  
> //创建一个读取excel函数
> function readExcel($path){
> 　　//引入PHPExcel类库
> 　　include 'Classes/PHPExcel.php';            
> 　　include 'Classes/PHPExcel/IOFactory.php';
> 
> 　　$type = 'Excel5';//设置为Excel5代表支持2003或以下版本，
> 　　Excel2007代表2007版
> 　　$xlsReader = PHPExcel_IOFactory::createReader($type);  
> 　　$xlsReader->setReadDataOnly(true);
> 　　$xlsReader->setLoadSheetsOnly(true);
> 　　$Sheets = $xlsReader->load($path);
> 　　//开始读取上传到服务器中的Excel文件，返回一个
> 　　二维数组
> 　　$dataArray = $Sheets->getSheet(0)->
> 　　toArray();
> 　　return $dataArray;
> }

## PHP写入示例代码编辑
> //设置PHPExcel类库的include path
> set_include_path('.'. PATH_SEPARATOR .'D:\Zeal\PHP_LIBS' . PATH_SEPARATOR .get_include_path());
> 
> * 以下是使用示例，对于以 //// 开头的行是不同的可选方式，请根据实际需要
> * 打开对应行的注释。
> * 如果使用 Excel5 ，输出的内容应该是GBK编码。
> 
> //设置文档基本属性
> $objProps = $objExcel->getProperties();
> $objProps->setCreator("Zeal Li"); //设置作者
> //合并单元格
> $objActSheet->mergeCells('B1:C22');
> //分离单元格
> $objActSheet->unmergeCells('B1:C22');
> //*************************************
> //设置单元格样式
> //
> //设置宽度
> $objActSheet->getColumnDimension('B')->setAutoSize(true);
> $objActSheet->getColumnDimension('A')->setWidth(30);
> $objStyleA5 = $objActSheet->getStyle('A5');
> //设置单元格内容的数字格式。);
> $objDrawing = new PHPExcel_Worksheet_Drawing();
> $objDrawing->setName('ZealImg');

## 参考资料
	1.  PHPExcel - OpenXML - Read, Write and Create spreadsheet documents in PHP - Spreadsheet engine  ．Github官方介绍页面[引用日期2