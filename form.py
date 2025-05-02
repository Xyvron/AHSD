import streamlit as st
import pandas as pd
import uuid
import json
import requests
import gspread
from google.oauth2 import service_account


# Fungsi untuk format rupiah tanpa menggunakan locale
def format_rupiah(angka):
    try:
        angka = float(angka)
        # Format dengan pemisah ribuan dan 2 digit di belakang koma
        return f"Rp {angka:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "Rp 0,00"

def parse_rupiah(rupiah_str):
    try:
        # Menghapus karakter Rp dan spasi
        clean_str = rupiah_str.replace("Rp", "").strip()
        # Mengkonversi format Indonesia (koma sebagai desimal) ke format Python
        clean_str = clean_str.replace(".", "").replace(",", ".")
        # Hapus karakter non-numerik lainnya
        clean_str = ''.join(c for c in clean_str if c.isdigit() or c == '.')
        return float(clean_str)
    except Exception:
        return 0.0

# Fungsi untuk menghubungkan ke Google Sheets dan mengambil data
def get_materials_from_sheets():
    try:
        st.write("Mencoba mengambil data dari Google Sheets...")
        # Sesuaikan dengan path ke file credentials JSON Anda
        credentials_dict = json.loads(st.secrets["GSHEET_CREDENTIALS"])
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        
        # Buat client gspread
        client = gspread.authorize(credentials)
        
        # Buka spreadsheet berdasarkan ID (gunakan open_by_key, bukan open)
        spreadsheet = client.open_by_key('1H4ZP6d3vdxFl3CWAS4guBGmDm38MRh3Q_1bgaKg0SSk')
        
        # Pilih sheet pertama
        sheet = spreadsheet.sheet1
        
        # Ambil semua nilai termasuk header
        values = sheet.get_all_values()
        
        # Lewati baris header (baris pertama)
        data_rows = values[1:]
        
        # Format data untuk pencarian
        materials_data = {}
        for row in data_rows:
            if len(row) >= 2:  # Pastikan ada minimal 2 kolom
                name = row[0]  # Kolom A (nama bahan)
                try:
                    price = float(row[1])  # Kolom B (harga)
                    materials_data[name] = price
                except (ValueError, TypeError):
                    # Lewati jika nilai harga tidak bisa dikonversi ke float
                    continue
        st.write(f"Berhasil mengambil {len(materials_data)} item dari spreadsheet.")
        return materials_data
    except Exception as e:
        st.error(f"Gagal mengambil data dari Google Sheets: {str(e)}")
        return {}

# Fungsi untuk memfilter bahan berdasarkan kata kunci pencarian
def filter_materials(search_term):
    if not search_term:
        return []
    
    search_term = search_term.lower()
    filtered = [name for name in st.session_state.materials_database.keys() 
                if search_term in name.lower()]
    return filtered[:10]  # Batasi hasil pencarian

# Fungsi untuk menangani pemilihan material dari hasil pencarian
def handle_material_selection(material_name):
    if material_name in st.session_state.materials_database:
        st.session_state.selected_material = material_name
        st.session_state.current_material_name = material_name
        price = st.session_state.materials_database[material_name]
        st.session_state.current_material_price = format_rupiah(price)

# Inisialisasi state jika belum ada
if 'project_name' not in st.session_state:
    st.session_state.project_name = ""
if 'jobs' not in st.session_state:
    st.session_state.jobs = []
if 'current_job_name' not in st.session_state:
    st.session_state.current_job_name = ""
if 'current_job_quantity' not in st.session_state:
    st.session_state.current_job_quantity = 1.0
if 'current_materials' not in st.session_state:
    st.session_state.current_materials = []
if 'is_adding_material' not in st.session_state:
    st.session_state.is_adding_material = False
if 'current_material_name' not in st.session_state:
    st.session_state.current_material_name = ""
if 'current_material_price' not in st.session_state:
    st.session_state.current_material_price = ""
if 'current_material_coefficient' not in st.session_state:
    st.session_state.current_material_coefficient = 1.000
if 'temp_jobs' not in st.session_state:
    st.session_state.temp_jobs = []
if 'is_saved' not in st.session_state:
    st.session_state.is_saved = False
# State untuk mode edit
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'editing_job_index' not in st.session_state:
    st.session_state.editing_job_index = -1
if 'editing_material_index' not in st.session_state:
    st.session_state.editing_material_index = -1
if 'editing_job_type' not in st.session_state:
    st.session_state.editing_job_type = ""  # 'main' atau 'temp'
if 'editing_temp_job_index' not in st.session_state:
    st.session_state.editing_temp_job_index = -1
if 'materials_database' not in st.session_state:
    st.session_state.materials_database = get_materials_from_sheets()
if 'filtered_materials' not in st.session_state:
    st.session_state.filtered_materials = []
if 'selected_material' not in st.session_state:
    st.session_state.selected_material = None

# Fungsi untuk mulai menambahkan bahan
def start_add_material():
    st.session_state.is_adding_material = True
    st.session_state.current_material_name = ""
    st.session_state.current_material_price = ""
    st.session_state.current_material_coefficient = 1.000
    st.session_state.filtered_materials = []
    st.session_state.selected_material = None

# Fungsi untuk menyimpan bahan ke pekerjaan saat ini
def save_material():
    if st.session_state.current_material_name and st.session_state.current_material_price:
        if st.session_state.editing_material_index >= 0:
            # Edit material yang sudah ada
            st.session_state.current_materials[st.session_state.editing_material_index] = {
                'id': st.session_state.current_materials[st.session_state.editing_material_index]['id'],
                'name': st.session_state.current_material_name,
                'price': parse_rupiah(st.session_state.current_material_price),
                'coefficient': st.session_state.current_material_coefficient
            }
            st.session_state.editing_material_index = -1
        else:
            # Tambah material baru
            st.session_state.current_materials.append({
                'id': str(uuid.uuid4()),
                'name': st.session_state.current_material_name,
                'price': parse_rupiah(st.session_state.current_material_price),
                'coefficient': st.session_state.current_material_coefficient
            })
        
        st.session_state.current_material_name = ""
        st.session_state.current_material_price = ""
        st.session_state.current_material_coefficient = 1.000
        st.session_state.selected_material = None  # Reset material yang dipilih
        st.session_state.filtered_materials = []  # Reset hasil pencarian

# Fungsi untuk mulai mengedit material
def edit_material(index):
    material = st.session_state.current_materials[index]
    st.session_state.is_adding_material = True
    st.session_state.current_material_name = material['name']
    st.session_state.current_material_price = format_rupiah(material['price'])
    # Pastikan material memiliki nilai koefisien, gunakan 1.0 jika tidak ada
    if 'coefficient' in material:
        st.session_state.current_material_coefficient = material['coefficient']
    else:
        st.session_state.current_material_coefficient = 1.000
    st.session_state.editing_material_index = index
    st.session_state.selected_material = None  # Reset material yang dipilih
    st.session_state.filtered_materials = []  # Reset hasil pencarian

# Fungsi untuk menghapus material
def delete_material(index):
    st.session_state.current_materials.pop(index)

# Fungsi untuk menambahkan pekerjaan baru ke daftar utama
def add_job_to_temp():
    if st.session_state.current_job_name and st.session_state.current_materials:
        if st.session_state.editing_temp_job_index >= 0:
            # Edit pekerjaan yang sudah ada dalam daftar sementara
            st.session_state.temp_jobs[st.session_state.editing_temp_job_index] = {
                'id': st.session_state.temp_jobs[st.session_state.editing_temp_job_index]['id'],
                'name': st.session_state.current_job_name,
                'quantity': st.session_state.current_job_quantity,
                'materials': st.session_state.current_materials.copy()
            }
            st.session_state.editing_temp_job_index = -1
        else:
            # Tambah pekerjaan baru langsung ke daftar utama
            st.session_state.jobs.append({
                'id': str(uuid.uuid4()),
                'name': st.session_state.current_job_name,
                'quantity': st.session_state.current_job_quantity,
                'materials': st.session_state.current_materials.copy()
            })
        
        # Reset form untuk pekerjaan baru
        st.session_state.current_job_name = ""
        st.session_state.current_job_quantity = 1.0
        st.session_state.current_materials = []
        st.session_state.is_adding_material = False
        
        # Set status disimpan menjadi true
        st.session_state.is_saved = True
        
        # Reset mode edit jika sedang dalam mode edit
        st.session_state.edit_mode = False

# Fungsi untuk membatalkan input (reset form)
def cancel_continuous_input():
    st.session_state.current_job_name = ""
    st.session_state.current_job_quantity = 1.0
    st.session_state.current_materials = []
    st.session_state.is_adding_material = False
    st.session_state.edit_mode = False

# Fungsi untuk memulai pengeditan pekerjaan
def edit_job(index, job_type="main"):
    if job_type == "main":
        job = st.session_state.jobs[index]
        st.session_state.editing_job_index = index
    else:  # job_type == "temp"
        job = st.session_state.temp_jobs[index]
        st.session_state.editing_temp_job_index = index
    
    st.session_state.edit_mode = True
    st.session_state.editing_job_type = job_type
    st.session_state.current_job_name = job['name']
    st.session_state.current_job_quantity = job['quantity']
    st.session_state.current_materials = job['materials'].copy()

# Fungsi untuk menyimpan hasil pengeditan pekerjaan
def save_edited_job():
    if st.session_state.current_job_name and st.session_state.current_materials:
        if st.session_state.editing_job_type == "main" and st.session_state.editing_job_index >= 0:
            # Edit pekerjaan di daftar utama
            st.session_state.jobs[st.session_state.editing_job_index] = {
                'id': st.session_state.jobs[st.session_state.editing_job_index]['id'],
                'name': st.session_state.current_job_name,
                'quantity': st.session_state.current_job_quantity,
                'materials': st.session_state.current_materials.copy()
            }
        elif st.session_state.editing_job_type == "temp" and st.session_state.editing_temp_job_index >= 0:
            # Edit pekerjaan di daftar sementara
            st.session_state.temp_jobs[st.session_state.editing_temp_job_index] = {
                'id': st.session_state.temp_jobs[st.session_state.editing_temp_job_index]['id'],
                'name': st.session_state.current_job_name,
                'quantity': st.session_state.current_job_quantity,
                'materials': st.session_state.current_materials.copy()
            }
        
        # Reset form dan keluar dari mode edit
        st.session_state.current_job_name = ""
        st.session_state.current_job_quantity = 1.0
        st.session_state.current_materials = []
        st.session_state.is_adding_material = False
        st.session_state.edit_mode = False
        st.session_state.editing_job_index = -1
        st.session_state.editing_temp_job_index = -1
        st.session_state.editing_job_type = ""

# Fungsi untuk menghapus pekerjaan
def delete_job(index, job_type="main"):
    if job_type == "main":
        st.session_state.jobs.pop(index)
    else:  # job_type == "temp"
        st.session_state.temp_jobs.pop(index)

# Fungsi untuk mengirim data ke n8n
def send_to_n8n():
    # Siapkan data yang akan dikirim
    data = {
        "project_name": st.session_state.project_name,
        "jobs": []
    }
    
    total_budget = 0
    
    # Format data pekerjaan
    for job in st.session_state.jobs:
        job_total = 0
        materials_formatted = []
        
        for material in job['materials']:
            # Pastikan material memiliki coefficient, gunakan 1.0 jika tidak ada
            coef = material.get('coefficient', 1.000)
            material_price = material['price']
            total_material_price = material_price * coef
            
            job_total += total_material_price
            materials_formatted.append({
                "name": material['name'],
                "price": material_price,
                "price_formatted": format_rupiah(material_price),
                "coefficient": coef,
                "total_price": total_material_price,
                "total_price_formatted": format_rupiah(total_material_price)
            })
        
        # Total biaya pekerjaan (harga * quantity)
        job_cost = job_total * job['quantity']
        total_budget += job_cost
        
        data["jobs"].append({
            "name": job['name'],
            "quantity": job['quantity'],
            "materials": materials_formatted,
            "total_cost": job_cost,
            "total_cost_formatted": format_rupiah(job_cost)
        })
    
    # Tambahkan total anggaran
    data["total_budget"] = total_budget
    data["total_budget_formatted"] = format_rupiah(total_budget)
    
    # URL webhook n8n - Pastikan ini adalah URL webhook yang valid dari n8n
    webhook_url = "https://xyvron.app.n8n.cloud/webhook/26c673fb-77bd-4bdc-8ddf-19525499175c"
    
    try:
        # Kirim data ke n8n - Hapus komentar dari baris ini
        response = requests.post(webhook_url, json=data)
        
        # Periksa status respons
        if response.status_code == 200:
            st.success("Data berhasil dikirim!")
            st.write("Status respons:", response.status_code)
            
            # Tampilkan data yang dikirim
            with st.expander("Lihat Data yang Dikirim"):
                st.json(data)
            
            # Reset form
            st.session_state.project_name = ""
            st.session_state.jobs = []
            st.session_state.is_saved = False
        else:
            st.error(f"Terjadi kesalahan saat mengirim data. Status kode: {response.status_code}")
            st.error(f"Respons: {response.text}")
            
    except Exception as e:
        st.error(f"Terjadi kesalahan saat mengirim data: {str(e)}")

# Aplikasi Streamlit
st.title("Aplikasi Perhitungan Anggaran Proyek")

# Tombol refresh database
if st.button("Refresh Database Bahan/Upah"):
    st.session_state.materials_database = get_materials_from_sheets()
    st.success("Database berhasil diperbarui!")

# Input Nama Proyek
project_name = st.text_input("Nama Proyek", st.session_state.project_name)
st.session_state.project_name = project_name

# Form input pekerjaan selalu ditampilkan
if st.session_state.edit_mode:
    st.subheader("Edit Pekerjaan")
else:
    st.subheader("Tambah Pekerjaan")

# Form untuk pekerjaan baru atau edit pekerjaan
st.session_state.current_job_name = st.text_input("Nama Pekerjaan", st.session_state.current_job_name)
st.session_state.current_job_quantity = st.number_input(
    "Jumlah Pekerjaan", 
    min_value=0.0001, 
    max_value=9999.9999, 
    value=st.session_state.current_job_quantity,
    format="%.3f"  # Diubah menjadi 3 angka di belakang koma
)

# Tampilkan daftar bahan yang sudah ditambahkan
if st.session_state.current_materials:
    st.write("Bahan-bahan yang ditambahkan:")
    for idx, material in enumerate(st.session_state.current_materials):
        # Pastikan material memiliki coefficient, gunakan 1.0 jika tidak ada
        coef = material.get('coefficient', 1.000)
        material_price = material['price']
        total_price = material_price * coef
        
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            st.write(f"{idx+1}. {material['name']} - {format_rupiah(material_price)} × {coef:.3f} = {format_rupiah(total_price)}")
        with col2:
            if st.button("Edit", key=f"edit_material_{idx}"):
                edit_material(idx)
        with col3:
            if st.button("Hapus", key=f"delete_material_{idx}"):
                delete_material(idx)

# Form untuk menambahkan bahan
if not st.session_state.is_adding_material:
    if st.button("Tambah Bahan"):
        start_add_material()
else:
    if st.session_state.editing_material_index >= 0:
        st.subheader("Edit Bahan")
    else:
        st.subheader("Tambah Bahan")
        
    # Input pencarian untuk material
    search_term = st.text_input("Cari Jenis Bahan/Upah", key="material_search")
    if search_term:
        st.session_state.filtered_materials = filter_materials(search_term)
        
        if st.session_state.filtered_materials:
            st.write("Hasil Pencarian:")
            for material in st.session_state.filtered_materials:
                if st.button(f"{material} - {format_rupiah(st.session_state.materials_database[material])}", key=f"select_{material}"):
                    handle_material_selection(material)
        else:
            st.info("Tidak ada hasil yang ditemukan")

    # Tampilkan material yang dipilih
    if st.session_state.selected_material:
        st.write(f"Bahan/Upah Terpilih: **{st.session_state.selected_material}**")
        st.write(f"Harga: **{st.session_state.current_material_price}**")
        
        # Tidak perlu input harga lagi karena sudah dipilih dari database
        price_input = None
    else:
        # Opsi untuk input manual jika tidak ada di database
        st.session_state.current_material_name = st.text_input("Masukkan Bahan/Upah Manual", st.session_state.current_material_name)
        price_input = st.text_input("Harga (Rp)", st.session_state.current_material_price)
        
        # Format input harga dalam format Rupiah
        if price_input and price_input != st.session_state.current_material_price:
            try:
                # Hapus karakter non-numerik untuk konversi
                numeric_value = ''.join(c for c in price_input if c.isdigit() or c == '.')
                if numeric_value:
                    numeric_value = float(numeric_value)
                    st.session_state.current_material_price = format_rupiah(numeric_value)
                else:
                    st.session_state.current_material_price = price_input
            except Exception:
                st.session_state.current_material_price = price_input
            
    # Input koefisien dengan 3 angka di belakang koma
    st.session_state.current_material_coefficient = st.number_input(
        "Koefisien", 
        min_value=0.001, 
        max_value=9999.999, 
        value=st.session_state.current_material_coefficient,
        format="%.3f"
    )
    
    # Format input harga dalam format Rupiah jika ada
    if 'price_input' in locals() and price_input and price_input != st.session_state.current_material_price:
        try:
            # Hapus karakter non-numerik untuk konversi
            numeric_value = ''.join(c for c in price_input if c.isdigit() or c == '.')
            if numeric_value:
                numeric_value = float(numeric_value)
                st.session_state.current_material_price = format_rupiah(numeric_value)
            else:
                st.session_state.current_material_price = price_input
        except Exception:
            st.session_state.current_material_price = price_input
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Simpan Bahan"):
            save_material()
            st.session_state.is_adding_material = False
    with col2:
        if st.button("Tambah Bahan Lain"):
            save_material()
            # Tetap dalam mode menambahkan bahan
    with col3:
        if st.button("Batalkan", key="cancel_material"):
            st.session_state.is_adding_material = False
            st.session_state.current_material_name = ""
            st.session_state.current_material_price = ""
            st.session_state.current_material_coefficient = 1.000
            st.session_state.editing_material_index = -1

# Tombol untuk menambah/menyimpan pekerjaan
if st.session_state.current_job_name and st.session_state.current_materials:
    if st.session_state.edit_mode:
        if st.button("Simpan Perubahan"):
            save_edited_job()
        if st.button("Batalkan Pengeditan"):
            st.session_state.current_job_name = ""
            st.session_state.current_job_quantity = 1.0
            st.session_state.current_materials = []
            st.session_state.is_adding_material = False
            st.session_state.edit_mode = False
            st.session_state.editing_job_index = -1
            st.session_state.editing_temp_job_index = -1
            st.session_state.editing_job_type = ""
    else:
        if st.button("Tambah Pekerjaan"):
            add_job_to_temp()

# Tampilkan daftar pekerjaan yang sudah ada (dari daftar utama)
if st.session_state.jobs and not st.session_state.edit_mode:
    st.subheader("Daftar Pekerjaan yang Tersimpan")
    
    # Hitung total anggaran
    total_budget = 0
    
    for idx, job in enumerate(st.session_state.jobs):
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            st.write(f"**{idx+1}. {job['name']} - Jumlah: {job['quantity']}**")
        with col2:
            if st.button("Edit", key=f"edit_job_{idx}"):
                edit_job(idx, "main")
        with col3:
            if st.button("Hapus", key=f"delete_job_{idx}"):
                delete_job(idx, "main")
        
        with st.expander("Detail Bahan"):
            job_total = 0
            for mat_idx, material in enumerate(job['materials']):
                # Pastikan material memiliki coefficient, gunakan 1.0 jika tidak ada
                coef = material.get('coefficient', 1.000)
                material_price = material['price']
                total_material_price = material_price * coef
                
                st.write(f"{mat_idx+1}. {material['name']} - {format_rupiah(material_price)} × {coef:.3f} = {format_rupiah(total_material_price)}")
                job_total += total_material_price
            
            # Total biaya pekerjaan (harga * quantity)
            job_cost = job_total * job['quantity']
            total_budget += job_cost
            
            st.write(f"**Total Biaya Pekerjaan:** {format_rupiah(job_cost)}")
    
    # Tampilkan total anggaran
    st.subheader("Total Anggaran Proyek")
    st.write(f"{format_rupiah(total_budget)}")
    
    # Tampilkan ringkasan pekerjaan dan bahan
    st.subheader("Ringkasan Pekerjaan dan Bahan")
    
    for idx, job in enumerate(st.session_state.jobs):
        st.write(f"**Pekerjaan {idx+1}: {job['name']} (Jumlah: {job['quantity']})**")
        st.write("Bahan-bahan:")
        for mat_idx, material in enumerate(job['materials']):
            # Pastikan material memiliki coefficient, gunakan 1.0 jika tidak ada
            coef = material.get('coefficient', 1.000)
            material_price = material['price']
            total_material_price = material_price * coef
            
            st.write(f"- {material['name']} ({format_rupiah(material_price)} × {coef:.3f} = {format_rupiah(total_material_price)})")
        st.write("")  # Tambahkan baris kosong untuk memisahkan pekerjaan
    
    # Tampilkan tombol kirim ke n8n 
    if st.button("Kirim", key="send_to_n8n"):
        send_to_n8n()
