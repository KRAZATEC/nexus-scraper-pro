import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin, urlparse
import re
from collections import Counter
import json
import time

st.set_page_config(page_title="Nexus Scraper Pro", page_icon="🌐", layout="wide", initial_sidebar_state="expanded")

# --- Custom CSS injected for extra polish ---
st.markdown("""
<style>
    /* Metric Card Styling */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Header gradient */
    .main-header {
        background: -webkit-linear-gradient(45deg, #8A2BE2, #4169E1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        padding-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>🌐 Nexus Scraper Pro</h1>", unsafe_allow_html=True)
st.markdown("Fetch, analyze, and visualize web data with our advanced extraction engine.")

# --- Sidebar ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2111/2111628.png", width=60)
    st.header("Extraction Config")
    url = st.text_input("Target URL", "http://quotes.toscrape.com/", placeholder="https://example.com")
    
    st.markdown("---")
    st.subheader("Data Modules")
    extract_metadata = st.checkbox("SEO Metadata", value=True)
    extract_titles = st.checkbox("Headings (H1-H6)", value=True)
    extract_links = st.checkbox("Hyperlinks", value=True)
    extract_images = st.checkbox("Images", value=True)
    extract_paragraphs = st.checkbox("Text Content", value=True)
    extract_emails = st.checkbox("Emails (Regex)", value=True)
    
    st.markdown("---")
    st.info("Nexus Scraper Pro uses standard HTTP headers to mimic browser behavior.")

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

@st.cache_data(show_spinner=False, ttl=600)
def scrape_website(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text, response.status_code
    except Exception as e:
        return None, str(e)

if st.sidebar.button("🚀 Launch Scraper", use_container_width=True, type="primary"):
    if not url or not is_valid_url(url):
        st.error("Please enter a valid absolute URL (e.g., https://example.com).")
    else:
        # Progress bar simulation for UX
        progress_text = "Establishing connection..."
        my_bar = st.progress(0, text=progress_text)
        time.sleep(0.5)
        my_bar.progress(30, text="Fetching raw HTML...")
        
        html_content, status_info = scrape_website(url)
        
        if html_content:
            my_bar.progress(70, text="Parsing DOM structure...")
            soup = BeautifulSoup(html_content, 'html.parser')
            
            my_bar.progress(100, text="Extraction complete!")
            time.sleep(0.5)
            my_bar.empty()
            
            st.success(f"Successfully connected to **{urlparse(url).netloc}** (Status 200)")
            
            # --- Initialize Data Containers ---
            all_extracted_data = {}
            
            # --- Perform Extractions ---
            metadata, headings, links, images, paragraphs, words, emails = {}, [], [], [], [], [], []
            
            if extract_metadata:
                metadata['Title'] = soup.title.string if soup.title else 'N/A'
                for meta in soup.find_all('meta'):
                    name_attr = meta.get('name') or meta.get('property') or meta.get('itemprop')
                    if name_attr:
                        metadata[name_attr] = meta.get('content') or meta.get('value')
                all_extracted_data['metadata'] = metadata
            
            if extract_titles:
                for i in range(1, 7):
                    for tag in soup.find_all(f'h{i}'):
                        text = tag.get_text(separator=' ', strip=True)
                        if text:
                            headings.append({"Level": f"H{i}", "Text": text})
                all_extracted_data['headings'] = headings

            if extract_links:
                for link in soup.find_all('a'):
                    href = link.get('href') or link.get('data-href')
                    if href and not href.startswith(('javascript:', 'tel:')):
                        if href.startswith('mailto:'):
                            emails.append({"Email": href.replace('mailto:', '').split('?')[0]})
                        else:
                            full_url = urljoin(url, href)
                            text = link.get_text(separator=' ', strip=True) or link.get('title') or link.get('aria-label') or "N/A"
                            links.append({"Text": text, "URL": full_url})
                # deduplicate
                links = [dict(t) for t in {tuple(d.items()) for d in links}]
                all_extracted_data['links'] = links

            if extract_images:
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('srcset')
                    if src:
                        # Extract the first valid URL from srcset if needed
                        actual_src = src.split(',')[0].split(' ')[0] if ' ' in src else src
                        actual_src = urljoin(url, actual_src)
                        alt_text = img.get('alt') or img.get('title') or "N/A"
                        images.append({"Alt Text": alt_text, "Source URL": actual_src})
                # deduplicate
                images = [dict(t) for t in {tuple(d.items()) for d in images}]
                all_extracted_data['images'] = images

            if extract_paragraphs:
                # Look for text in p, span, div, li, article, section
                text_elements = soup.find_all(['p', 'span', 'li', 'article', 'section', 'div'])
                seen_texts = set()
                for el in text_elements:
                    # Ignore scripts, styles, and empty elements
                    if el.name in ['script', 'style']: continue
                    
                    # Ensure we only get non-empty text
                    text = el.get_text(separator=' ', strip=True)
                    # To avoid grabbing massive div blocks where children were already grabbed, limit string matching
                    # A better way is to only grab elements where direct string descendants exist and are substantial
                    own_text = ''.join(el.find_all(string=True, recursive=False)).strip()
                    
                    if len(own_text) > 20 and own_text not in seen_texts:
                        seen_texts.add(own_text)
                        paragraphs.append({"Text": own_text, "Length": len(own_text), "Tag": el.name})
                        words.extend(re.findall(r'\b\w+\b', own_text.lower()))
                        
                all_extracted_data['paragraphs'] = paragraphs
                
            if extract_emails:
                # Basic email regex on the entire document text instead of HTML content to avoid matching false positives
                # But HTML content might have href="mailto:", which we already handled
                doc_text = soup.get_text(separator=' ')
                email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
                found_emails = set(re.findall(email_pattern, doc_text))
                
                # Combine regex emails with mailto emails
                existing_email_strs = {e['Email'] for e in emails}
                for e in found_emails:
                    if e not in existing_email_strs:
                        emails.append({"Email": e})
                all_extracted_data['emails'] = emails

            # --- Metrics Dashboard ---
            st.markdown("### 📊 Dashboard Overview")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Headings Found", len(headings) if extract_titles else "N/A", delta="SEO" if extract_titles else None)
            with col2:
                st.metric("Links Extracted", len(links) if extract_links else "N/A", delta="Navigation" if extract_links else None)
            with col3:
                st.metric("Images Detected", len(images) if extract_images else "N/A", delta="Media" if extract_images else None)
            with col4:
                st.metric("Paragraphs Analyzed", len(paragraphs) if extract_paragraphs else "N/A", delta="Content" if extract_paragraphs else None)

            st.markdown("---")

            # --- Detailed Tabs ---
            tab_names = ["SEO Meta", "Headings", "Links & Nav", "Media", "Content & NLP", "Emails"]
            tabs = st.tabs(tab_names)

            # Metadata Tab
            with tabs[0]:
                if extract_metadata:
                    st.subheader("SEO & Meta Information")
                    if metadata:
                        df_meta = pd.DataFrame(list(metadata.items()), columns=["Property", "Content"])
                        st.table(df_meta)
                    else:
                        st.info("No meta tags found.")
                else:
                    st.warning("Metadata extraction disabled.")

            # Headings Tab
            with tabs[1]:
                if extract_titles:
                    col_h1, col_h2 = st.columns([1, 2])
                    with col_h1:
                        st.subheader("Structure")
                        h_counts = Counter([h['Level'] for h in headings])
                        if h_counts:
                            st.bar_chart(pd.DataFrame.from_dict(h_counts, orient='index', columns=['Count']))
                    with col_h2:
                        st.subheader("Raw Data")
                        if headings:
                            st.dataframe(pd.DataFrame(headings), use_container_width=True)
                        else:
                            st.info("No headings found.")
                else:
                    st.warning("Heading extraction disabled.")

            # Links Tab
            with tabs[2]:
                if extract_links:
                    st.subheader("Extracted Hyperlinks")
                    if links:
                        st.dataframe(pd.DataFrame(links), use_container_width=True)
                    else:
                        st.info("No links found.")
                else:
                    st.warning("Link extraction disabled.")

            # Images
            with tabs[3]:
                if extract_images:
                    col_img1, col_img2 = st.columns([2, 1])
                    with col_img1:
                        st.subheader("Image Assets")
                        if images:
                            st.dataframe(pd.DataFrame(images), use_container_width=True)
                        else:
                            st.info("No images found.")
                    with col_img2:
                        # Show a preview of the first image if available
                        if images and images[0]['Source URL'].startswith('http'):
                            st.image(images[0]['Source URL'], caption="Preview of first image found", use_container_width=True)
                else:
                    st.warning("Image extraction disabled.")

            # Content Tab
            with tabs[4]:
                if extract_paragraphs:
                    col_txt1, col_txt2 = st.columns([1, 1])
                    with col_txt1:
                        st.subheader("Paragraph Content")
                        if paragraphs:
                            st.dataframe(pd.DataFrame(paragraphs), use_container_width=True)
                        else:
                            st.info("No paragraphs found.")
                    with col_txt2:
                        st.subheader("Top Word Frequencies")
                        if words:
                            # Filter out very common short words
                            stop_words = {'the', 'and', 'to', 'of', 'a', 'in', 'is', 'that', 'for', 'it', 'on', 'with', 'as', 'this', 'was', 'at', 'by', 'an'}
                            filtered_words = [w for w in words if w not in stop_words and w.isalpha() and len(w) > 2]
                            top_words = Counter(filtered_words).most_common(15)
                            if top_words:
                                df_words = pd.DataFrame(top_words, columns=['Word', 'Frequency']).set_index('Word')
                                st.bar_chart(df_words)
                            else:
                                st.info("Not enough meaningful words to chart.")
                        else:
                            st.info("No words to analyze.")
                else:
                    st.warning("Paragraph extraction disabled.")

            # Emails Tab
            with tabs[5]:
                if extract_emails:
                    st.subheader("Email Addresses")
                    if emails:
                        st.dataframe(pd.DataFrame(emails), use_container_width=True)
                    else:
                        st.info("No email addresses detected on this page.")
                else:
                    st.warning("Email extraction disabled.")

            st.markdown("---")
            
            # --- Export Section ---
            st.subheader("📥 Export Data")
            export_col1, export_col2 = st.columns(2)
            
            with export_col1:
                json_data = json.dumps(all_extracted_data, indent=4)
                st.download_button(
                    label="Download All Data as JSON",
                    data=json_data,
                    file_name=f"{urlparse(url).netloc}_data.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with export_col2:
                if extract_links and links:
                    csv_links = pd.DataFrame(links).to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Links (CSV)",
                        data=csv_links,
                        file_name=f"{urlparse(url).netloc}_links.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.download_button("Download Links (CSV)", data="", disabled=True, use_container_width=True)

        else:
            st.error(f"Failed to fetch data: {status_info}")
