# using python version 3+
# in terminal run -> python3 -m venc venv
# in terminal run -> source venv/bin/activate
# install required librabries 
# in terminal run -> pip install playwright, scipy, matplotlib
# in terminal run -> playwright install
# in terminal run -> python3 -u burgerbae_mapped2.py


import os
import csv
import hashlib
import time
from urllib.parse import urlparse
from collections import deque, defaultdict

from playwright.sync_api import sync_playwright
import networkx as nx
import matplotlib.pyplot as plt

# === CONFIG ===
START_URL = "https://www.burgerbaeclothing.com/"
OUTPUT_ROOT = "burgerbae_mapped2"
MAX_PAGES = 20
CSV_FILE = os.path.join(OUTPUT_ROOT, "crawl_assets.csv")

graph_edges = defaultdict(set)  # For crawl graph


# === HELPERS ===

def sanitize_folder_name(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    folder_name = path.replace("/", "_") or "index"
    return folder_name


def is_internal_link(base_url, link_url):
    return urlparse(base_url).netloc == urlparse(link_url).netloc


def extract_internal_links(base_url, page):
    links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    return [link for link in links if is_internal_link(base_url, link)]


def extract_images_and_links(page):
    imgs = page.eval_on_selector_all("img[src]", "els => els.map(e => e.src)")
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    return imgs, hrefs


def save_html(folder, html):
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, os.path.basename(folder) + ".html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)


def append_to_csv(csv_path, page_url, images, links):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if write_header:
            writer.writerow(["Page URL", "Image SRC", "Link HREF"])
        for img in images:
            writer.writerow([page_url, img, ""])
        for href in links:
            writer.writerow([page_url, "", href])


def hash_url(url):
    return hashlib.sha256(url.encode()).hexdigest()


def draw_crawl_graph(graph_data, output_path="crawl_graph.png", max_labels=20):
    G = nx.DiGraph()
    for src, dsts in graph_data.items():
        for dst in dsts:
            G.add_edge(src, dst)

    plt.figure(figsize=(20, 15))
    pos = nx.kamada_kawai_layout(G)

    # Draw nodes and edges
    nx.draw_networkx_nodes(G, pos, node_size=50, node_color='skyblue', alpha=0.8)
    nx.draw_networkx_edges(G, pos, alpha=0.4, arrows=True)

    # Label only top N most connected pages
    degrees = dict(G.degree())
    top_nodes = sorted(degrees, key=degrees.get, reverse=True)[:max_labels]
    labels = {node: node for node in top_nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=6)

    plt.title("Simplified Crawl Graph")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    print(f"📊 Crawl graph saved to {output_path}")


# === MAIN CRAWLER ===

def crawl_site(start_url):
    visited = set()
    queue = deque([start_url])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.set_default_navigation_timeout(60000)

        while queue and len(visited) < MAX_PAGES:
            url = queue.popleft()
            if hash_url(url) in visited:
                continue

            try:
                print(f"[+] Visiting: {url}")
                page = context.new_page()
                page.goto(url, timeout=60000)
                try:
                    page.wait_for_load_state("networkidle", timeout=60000)
                except Exception:
                    print(" Network idle wait timed out, proceeding anyway")

                time.sleep(1)  # Let content load

                folder_name = sanitize_folder_name(url)
                folder_path = os.path.join(OUTPUT_ROOT, folder_name)

                html = page.content()
                save_html(folder_path, html)

                images, links = extract_images_and_links(page)
                append_to_csv(CSV_FILE, url, images, links)

                new_links = extract_internal_links(start_url, page)
                for link in new_links:
                    graph_edges[url].add(link)
                    if hash_url(link) not in visited:
                        queue.append(link)

                visited.add(hash_url(url))
                page.close()

            except Exception as e:
                print(f"[!] Error visiting {url}: {e}")

        browser.close()


# === ENTRY POINT ===

if __name__ == "__main__":
    start_time = time.time()

    crawl_site(START_URL)

    total_time = time.time() - start_time

    print(f"\n Crawl complete. HTML saved in '{OUTPUT_ROOT}/', assets listed in '{CSV_FILE}'")
    print(f"Total time taken: {total_time:.2f} seconds")

    graph_path = os.path.join(OUTPUT_ROOT, "crawl_graph.png")
    draw_crawl_graph(graph_edges, output_path=graph_path)
