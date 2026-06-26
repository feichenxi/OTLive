/** 用户数据统计模块 */
layui.define(function(exports){
  layui.use(["admin","carousel"],function(){
    var $ = layui.$,
        admin = layui.admin,
        carousel = layui.carousel,
        element = layui.element,
        device = layui.device();
    
    $(".layadmin-carousel").each(function(){
      var othis = $(this);
      carousel.render({
        elem: this,
        width: "100%",
        arrow: "none",
        interval: othis.data("interval"),
        autoplay: othis.data("autoplay") === true,
        trigger: (device.ios || device.android) ? "click" : "hover",
        anim: othis.data("anim")
      });
    });
    
    element.render("progress");
  });
  
  layui.use(["echarts"],function(){
    var $ = layui.$,
        echarts = layui.echarts;
    
    // 用户增长数据
    var userGrowthOption = {};
    
    // 如果有用户数据，则使用用户数据，否则使用默认数据
    if (window.userGrowthData) {
      userGrowthOption = {
        title: {
          text: "最近30天用户增长趋势",
          x: "center",
          textStyle: {
            fontSize: 14
          }
        },
        tooltip: {
          trigger: "axis"
        },
        xAxis: {
          type: "category",
          boundaryGap: false,
          data: window.userGrowthData.dates
        },
        yAxis: {
          type: "value"
        },
        series: [{
          name: "新增用户",
          type: "line",
          smooth: true,
          itemStyle: {
            normal: {
              areaStyle: {
                type: "default"
              }
            }
          },
          data: window.userGrowthData.userData
        }]
      };
      
      // 等待DOM加载完成
      $(document).ready(function() {
        var element = document.getElementById("user-growth-chart");
        if (element) {
          // 初始化图表
          var chart = echarts.init(element, layui.echartsTheme);
          chart.setOption(userGrowthOption);
          
          // 窗口大小改变时重置图表大小
          window.onresize = function() {
            chart.resize();
          };
        }
      });
    }
  });
  
  exports("userConsole", {});
});