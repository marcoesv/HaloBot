import base64
import aiohttp
import asyncio

# Allowed file types for attachments (images only)
ALLOWED_IMAGE_TYPES = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES

# File size limit (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024

async def process_attachments(attachments):
    """Process attachments from Bot Framework and convert to base64"""
    if not attachments:
        return None
    
    processed_files = []
    
    for attachment in attachments:
        try:
            # Validate file type
            filename = attachment.name or "file"
            file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
            
            if file_extension not in ALLOWED_TYPES:
                return {
                    "error": f"❌ File type '.{file_extension}' not supported. Please upload screenshots (PNG, JPG, GIF, etc.) only.\n💡 For documents, upload to OneDrive and share the link in your message."
                }
            
            # Download file content
            file_content = await download_attachment(attachment)
            if not file_content:
                return {"error": "❌ Failed to download the attached file. Please try again."}
            
            # Check file size
            if len(file_content) > MAX_FILE_SIZE:
                return {"error": f"❌ File '{filename}' is too large. Maximum size is 5MB."}
            
            # Convert to base64
            file_data = file_to_base64(file_content, filename)
            processed_files.append(file_data)
            
        except Exception as e:
            print(f"Error processing attachment: {e}")
            return {"error": "❌ Error processing the attached file. Please try again."}
    
    return {"files": processed_files}

async def download_attachment(attachment):
    """Download attachment content from URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.content_url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    print(f"Failed to download attachment: {response.status}")
                    return None
    except Exception as e:
        print(f"Error downloading attachment: {e}")
        return None

def file_to_base64(file_content, filename):
    """Convert file content to base64 string"""
    encoded = base64.b64encode(file_content).decode('utf-8')
    return {
        "filename": filename,
        "content": encoded,
        "mime_type": get_mime_type(filename)
    }

def get_mime_type(filename):
    """Get MIME type from filename extension"""
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    mime_types = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'webp': 'image/webp'
    }
    return mime_types.get(extension, 'application/octet-stream')

def create_image_html(base64_content, mime_type, filename, width=500):
    """Create HTML img tag with base64 content for Halo details_html"""
    return f'<br><p><strong>Attached Screenshot: {filename}</strong></p><img src="data:{mime_type};base64,{base64_content}" width="{width}"><br>'

def add_attachments_to_details_html(details_html, attachments_data):
    """Add attachment HTML to the existing details_html"""
    if not attachments_data or not attachments_data.get("files"):
        return details_html
    
    attachment_html = ""
    for file_data in attachments_data["files"]:
        attachment_html += create_image_html(
            file_data["content"],
            file_data["mime_type"],
            file_data["filename"]
        )
    
    # Add attachments after the user table but before other content
    if "</table>" in details_html:
        parts = details_html.split("</table>", 1)
        return parts[0] + "</table>" + attachment_html + parts[1]
    else:
        return details_html + attachment_html
