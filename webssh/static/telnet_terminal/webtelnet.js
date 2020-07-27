function get_connect_info() {

    var params = {
        "host":"localhost",
        "port":"23",
        "user":"root",
        "pwd":"root"
    };
    var querys = window.location.href.split("?")[1].split("&")
    for(var i=0;i<querys.length;i++)
    {
        var _i = querys[i].indexOf("=")
        if(_i==-1)
        {
            $("#terminal").text("Invaild Query Params！")
            break;
        }
        var key = querys[i].substr(0,_i)
        var val = querys[i].substr(_i+1)
        if(!params[key])continue;
        params[key] = val
    }

    var host = $.trim(params["host"]);
    var port = $.trim(params["port"]);
    var user = $.trim(params["user"]);
    var pwd = $.trim(params["pwd"]);
    var password = window.btoa(pwd);

    var connect_info = 'host=' + host + '&port=' + port + '&user=' + user + '&password=' + password;
    return connect_info
}


function get_term_size() {
    var init_width = 9;
    var init_height = 17;

    var windows_width = $(window).width();
    var windows_height = $(window).height();

    return {
        cols: Math.floor(windows_width / init_width),
        rows: Math.floor(windows_height / init_height),
    }
}


function websocket() {
    var cols = get_term_size().cols;
    var rows = get_term_size().rows;
    var connect_info = get_connect_info();

    var term = new Terminal(
        {
            cols: cols,
            rows: rows,
            useStyle: true,
            cursorBlink: true
        }
        ),
        protocol = (location.protocol === 'https:') ? 'wss://' : 'ws://',
        socketURL = protocol + location.hostname + ((location.port) ? (':' + location.port) : '') + '/telnet?' + connect_info;

    var sock;
    sock = new WebSocket(socketURL);

    // 打开 websocket 连接, 打开 web 终端
    sock.addEventListener('open', function () {
        $('#form').addClass('hide');
        $('#django-webtelnet-terminal').removeClass('hide');
        term.open(document.getElementById('terminal'));
		term.focus();
		$("body").attr("onbeforeunload",'checkwindow()'); //增加刷新关闭提示属性
		
    });

    // 读取服务器端发送的数据并写入 web 终端
    sock.addEventListener('message', function (recv) {
        var data = JSON.parse(recv.data);
        var message = data.message;
        var status = data.status;
        if (status === 0) {
            term.write(message)
        } else {
            //window.location.reload() 端口连接后刷新页面
			//term.clear()
			term.write(message)
			$("body").removeAttr("onbeforeunload"); //删除刷新关闭提示属性
			
			//$(document).keyup(function(event){	// 监听回车按键事件
			//	if(event.keyCode == 13){
					//window.location.reload();
			//	}
			//});
			//term.dispose()
			//$('#django-webssh-terminal').addClass('hide');
			//$('#form').removeClass('hide');
        }
    });
    sock.addEventListener('close',function()
    {
        $("#terminal").html("connection lost!")
    });

    /*
    * status 为 0 时, 将用户输入的数据通过 websocket 传递给后台, data 为传递的数据, 忽略 cols 和 rows 参数
    */
    var message = {'status': 0, 'data': null, 'cols': null, 'rows': null};

    // 向服务器端发送数据
    term.on('data', function (data) {
        message['status'] = 0;
        message['data'] = data;
        var send_data = JSON.stringify(message);
        sock.send(send_data)
    });

    // 监听浏览器窗口, 根据浏览器窗口大小修改终端大小
    $(window).resize(function () {
        var cols = get_term_size().cols;
        var rows = get_term_size().rows;
        term.resize(cols, rows)
    })
}

$(function()
{
    websocket();
})