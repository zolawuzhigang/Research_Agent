import docx

def read_docx(file_path):
    """
    读取DOCX文件的内容
    """
    try:
        doc = docx.Document(file_path)
        content = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                content.append(paragraph.text)
        return "\n".join(content)
    except Exception as e:
        print(f"读取DOCX文件失败: {e}")
        return None

if __name__ == "__main__":
    file_path = "Research_Agent项目优化方案报告（适配阿里云天池竞赛）.docx"
    content = read_docx(file_path)
    if content:
        print(content)
    else:
        print("无法读取文件内容")
