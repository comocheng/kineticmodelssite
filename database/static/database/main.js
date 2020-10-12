function copy() {
    var input = document.querySelector("#input");
    if (document.body.createTextRange) {
        const range = document.body.createTextRange();
        range.moveToElementText(input);
        range.select();
    } else if (window.getSelection) {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(input);
        selection.removeAllRanges();
        selection.addRange(range);
    } else {
        console.warn("Could not select text in node: Unsupported browser.");
    }
    document.execCommand("copy")
}

var button = document.querySelector("#copy")
button.addEventListener("click", copy)
