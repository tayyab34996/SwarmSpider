import asyncio
from aiohttp import web
import random

async def handle_page(request):
    page_id = request.match_info.get('id', '1')
    try:
        page_id_int = int(page_id)
    except ValueError:
        return web.Response(status=400, text="Invalid page ID")

    # Simulate random latency (10ms to 100ms)
    await asyncio.sleep(random.uniform(0.01, 0.1))

    # Simulate intermittent failures on specific pages to test retry logic
    # Every 15th page has a 50% chance of failing
    if page_id_int % 15 == 0 and random.random() < 0.5:
        return web.Response(status=500, text="Internal Server Error")
    
    # Simulate very slow page for timeout testing
    if page_id_int % 25 == 0:
        await asyncio.sleep(2.0)
        
    # Every 17th page is malformed to test extraction failure isolation
    if page_id_int % 17 == 0:
        return web.Response(text="<html><body>Bad Data No Fields</body></html>", content_type='text/html')

    # Generate some mock HTML content
    html_content = f"""
    <html>
        <head><title>Product {page_id_int}</title></head>
        <body>
            <div class="product">
                <h1 id="title">Awesome Product {page_id_int}</h1>
                <p id="price">${(page_id_int * 1.5) % 100:.2f}</p>
                <p id="stock">{"In Stock" if page_id_int % 3 != 0 else "Out of Stock"}</p>
                <div id="description">This is a great product. ID: {page_id_int}.</div>
            </div>
        </body>
    </html>
    """
    
    return web.Response(text=html_content, content_type='text/html')

async def handle_index(request):
    # Endpoint to discover all pages, we'll assume 120 pages total for the assignment
    links = [f'<a href="/page/{i}">Page {i}</a>' for i in range(1, 121)]
    html = f"<html><body>{'<br>'.join(links)}</body></html>"
    return web.Response(text=html, content_type='text/html')

app = web.Application()
app.add_routes([
    web.get('/', handle_index),
    web.get('/page/{id}', handle_page)
])

if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=8080)
