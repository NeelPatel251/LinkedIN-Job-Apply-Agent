chrome.commands.onCommand.addListener((command) => {
  if (command === "open-sidebar") {
    chrome.sidebarAction.open();
  }
});
