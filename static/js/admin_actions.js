/**
 * Admin Actions - Delete Confirmation
 * 处理后台删除操作的确认逻辑，替代内联 onclick，符合 CSP 安全策略。
 */

document.addEventListener('DOMContentLoaded', function() {
    // 监听所有带有 'delete-confirm' 类的元素
    const deleteButtons = document.querySelectorAll('.delete-confirm');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            // 1. 阻止超链接的默认跳转行为
            event.preventDefault();
            
            // 2. 获取数据
            const categoryName = this.getAttribute('data-name');
            const deleteUrl = this.getAttribute('href');
            
            // 3. 构建确认信息
            const message = `确定要删除分类【${categoryName}】吗？\n同时会删除该分类下的所有商品及图片！`;
            
            // 4. 弹出确认框
            if (confirm(message)) {
                // 用户点击“确定”后，手动跳转到删除链接
                window.location.href = deleteUrl;
            }
        });
    });
});