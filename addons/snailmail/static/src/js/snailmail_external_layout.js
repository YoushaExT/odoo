// Change address font-size if needed
document.addEventListener('DOMContentLoaded', function (evt) {
    var recipientAddress = document.querySelector(".address.row > div[name='address'] > div")
    var style = window.getComputedStyle(recipientAddress, null); 
    var height = parseFloat(style.getPropertyValue('height'));
    var fontSize = parseFloat(style.getPropertyValue('font-size'));
    recipientAddress.style.fontSize = (85 / (height / fontSize)) + 'px';   
});