//added by pht
var send = document.getElementById("send");
var submit = document.getElementById("submit");
var form = document.getElementById("form");
var send_captcha = document.getElementById("send_captcha");
var countdown=60;

function settime() {
	if (countdown == 0) {
		send.removeAttribute("disabled");
		send.innerHTML="发送验证码";
		countdown = 60;
	} else {
		send.setAttribute("disabled", true);
		send.innerHTML="重新发送(" + countdown + ")";
		countdown--;
		setTimeout("settime()",1000);
	}
}

if (send) {
	send.addEventListener('click', function() {
		settime();
		send_captcha.value='yes';
	});
}
if (submit) {
	submit.addEventListener('click', function() {
		send_captcha.value='no';
	});
}