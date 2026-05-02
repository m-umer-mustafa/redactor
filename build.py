import PyInstaller.__main__
import os
import shutil

if __name__ == '__main__':
    print("Cleaning previous builds...")
    for clean_dir in ['build', 'dist']:
        if os.path.exists(clean_dir):
            shutil.rmtree(clean_dir)

    print("Starting PyInstaller compilation...")
    PyInstaller.__main__.run([
        'main.py',
        '--name=Redactor',
        '--windowed',
        '--icon=icon.ico',
        '--onedir',
        '--noconfirm',
        '--hidden-import=spacy',
        '--hidden-import=en_core_web_lg',
        '--hidden-import=presidio_analyzer',
        '--hidden-import=presidio_anonymizer',
        '--collect-data=spacy',
        '--collect-data=en_core_web_lg',
        '--collect-data=presidio_analyzer',
        '--collect-data=presidio_anonymizer',
        '--copy-metadata=spacy',
        '--copy-metadata=en_core_web_lg',
        '--copy-metadata=presidio_analyzer',
        '--hidden-import=fitz',
        '--hidden-import=docx',
        '--hidden-import=mixpanel',
        '--add-data=icon.ico;.'
    ])
    print("Build complete! Check the dist/Redactor folder.")
