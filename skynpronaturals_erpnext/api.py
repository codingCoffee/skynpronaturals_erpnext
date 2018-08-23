from __future__ import unicode_literals
import frappe, json
import frappe
from frappe import _
from frappe.desk.reportview import get_match_cond
from erpnext.controllers.queries import get_filters_cond

@frappe.whitelist()
def validate_sales_invoice(self, method):

	spn_warehouse = frappe.db.get_value("Sales Invoice","spn_warehouse")
	cust_ter = frappe.db.get_value("Sales Invoice","territory")
	cust_group = frappe.db.get_value("Sales Invoice","customer_group")

	if not self.naming_series:
		self.naming_series = get_naming_series(spn_warehouse,cust_ter,cust_group)

	#Disallow back-dated sales invoices
	# if frappe.utils.getdate(self.posting_date) < frappe.utils.datetime.date.today():
	# 	frappe.throw("Please set the posting date to either today's date or a future date.<br> Back-dated invoices are not allowed.")

@frappe.whitelist()
def validate_stock_entry(self, method):
	if self.spn_linked_transit_entry:
		#linked_entry = frappe.get_doc("Stock Entry","spn_linked_transit_entry")
		for d in self.get('items'):
			linked_entry_item_qty = frappe.db.get_value("Stock Entry Detail", filters={"parent": self.spn_linked_transit_entry, "item_code": d.item_code}, fieldname= "qty")
			if linked_entry_item_qty < d.qty-((d.spn_rejected_qty or 0.0) + (d.spn_qty_lost or 0.0)):
				frappe.throw(_(" Item Qty should not exceed quantity in transit" ))


@frappe.whitelist()
def validate_purchase_receipt(self, method):
		#linked_entry = frappe.get_doc("Stock Entry","spn_linked_transit_entry")
		for d in self.get('items'):
			# linked_entry_item_qty = frappe.db.get_value("Stock Entry Detail", filters={"parent": self.spn_linked_transit_entry, "item_code": d.item_code}, fieldname= "qty")
			if d.rejected_qty != d.spn_rejected_qty + d.spn_transit_loss_qty:
				frappe.throw(_("Row #{0}: Item Qty should not exceed quantity in transit {1}").format(d.idx, d.item_code))


@frappe.whitelist()
def get_naming_series(spn_warehouse, cust_ter, cust_group):

	warehouse_state = frappe.db.get_value("Warehouse", spn_warehouse, "state")

	if warehouse_state.lower() == "assam":
		if cust_group=="Assam Registered Distributor" and cust_ter == "Assam":
			return "GV-.#####"
		elif cust_group=="Assam Unregistered Distributor":
			return "GU-.#####"
		else:
			return "GC-.#####"
	elif warehouse_state.lower() == "maharashtra":
		if cust_group=="Maharashtra Registered Distributor" and cust_ter == "Maharashtra":
			return "BV-.#####"
		elif cust_group=="Maharashtra Unregistered Distributor":
			return "BU-.#####"
		else:
			return "BC-.#####"
	elif warehouse_state.lower() == "west bengal":
		if cust_group=="West Bengal Registered Distributor" and cust_ter == "West Bengal":
			return "WBV-.#####"
		elif cust_group=="West Bengal Unregistered Distributor":
			return "WBU-.#####"
		else:
			return "WBC-.#####"


	# for x in xrange(1,10):
	# 	#print "WAREHOUSE: ", spn_warehouse, " CUST_TER: ", cust_ter, "CUST_GROUP: ", cust_group 
	# 	print warehouse_state.lower()

	# elif warehouse_state.lower() == "west bengal"
	# 	if cust_group=="West Bengal Registered Distributor" and cust_ter == "West Bengal":
	# 		return "WBV-.#####"
	# 	elif cust_group=="West Bengal Unregistered Distributor":
	# 		return "WBU-.#####"
	# 	else:
	# 		return "WBC-.#####"


@frappe.whitelist()
def get_terms_by_warehouse_state(spn_warehouse):

	warehouse_state = frappe.db.get_value("Warehouse", spn_warehouse, "state")
	existing_territory = frappe.db.get_value("Territory", warehouse_state)

	if not existing_territory:
		frappe.throw("Could not find corresponding Territory for Warehouse State {0}".format(warehouse_state))

	tc_name = frappe.db.get_value("Terms and Conditions", {"spn_territory": warehouse_state})

	# frappe.msgprint({"Warehouse State": warehouse_state, "Existing Territory": existing_territory, "TC Name": tc_name})
	return tc_name


@frappe.whitelist()
def get_spn_letter_head(spn_warehouse):
	return frappe.db.get_value("Warehouse",spn_warehouse,"spn_letterhead")
	# if spn_warehouse == "Bellezimo Professionale Products Pvt. Ltd. - SPN":
	#     if cust_group=="Assam Registered Distributor" and cust_ter == "Assam":
	#         return "GV-.#####"
	#     elif cust_group=="Assam Unregistered Distributor":
	#         return "GU-.#####"
	#     else:
	#         return "GC-.#####"
	# elif spn_warehouse == "Bellezimo Professionale Products Pvt. Ltd. C/o. Kotecha Clearing & Forwarding Pvt. Ltd.  - SPN":
	#     if cust_group=="Maharashtra Registered Distributor" and cust_ter == "Maharashtra":
	#         return "BV-.#####"
	#     elif cust_group=="Maharashtra Unregistered Distributor":
	#         return "BU-.#####"
	#     else:
	#         return "BC-.#####"



@frappe.whitelist()
def get_details_from_transit_entry(transit_entry_name):
	#from frappe.model.mapper import get_mapped_doc
	transit_entry = frappe.get_doc("Stock Entry", transit_entry_name)
	return {"destination_warehouse": transit_entry.spn_to_warehouse, "items": transit_entry.items}


@frappe.whitelist()
def create_transit_loss_stock_entry(transit_entry_name):
	pass

def stock_entry_on_submit(self, method):
	make_new_stock_entry(self, method)
	make_new_reject_entry(self, method)

#Make material issue instead of transfer as the loss entry:
def make_new_stock_entry(self, method):
	items_with_loss_qty = [i for i in self.get('items') if i.spn_qty_lost > 0.0]
	if len(items_with_loss_qty) > 0:
		
		wh_src = frappe.db.get_value("SPN Settings","SPN Settings","spn_transit_warehouse")
			
		if self.spn_linked_transit_entry and self.from_warehouse == wh_src: #and self.to_warehouse != wh_loss:
			s = frappe.new_doc("Stock Entry")
			s.posting_date = self.posting_date
			s.posting_time = self.posting_time

			if not self.company:
				if self.source:
					self.company = frappe.db.get_value('Warehouse', self.from_warehouse, 'company')
		
			s.purpose = "Material Issue"# Transfer"
			s.spn_linked_transit_entry = self.name

			s.company = self.company or erpnext.get_default_company()
			for item in [item for item in self.items if (item.spn_qty_lost > 0)]:
				
				s.append("items", {
					"item_code": item.item_code,
					"s_warehouse": wh_src,
					"qty": item.spn_qty_lost,
					"basic_rate": item.basic_rate,
					"conversion_factor": 1.0,
					"serial_no": item.serial_no,
					'cost_center': item.cost_center,
					'expense_account': item.expense_account
				})

			s.save()
			s.submit()
			frappe.db.commit()

def make_new_reject_entry(self, method):

	for x in xrange(1,5):
		print ("REJECT")

	items_with_loss_qty = [i for i in self.get('items') if i.spn_rejected_qty> 0.0]
	if len(items_with_loss_qty) > 0:
		
		wh_src = frappe.db.get_value("SPN Settings","SPN Settings","spn_transit_warehouse")

		if self.spn_linked_transit_entry and self.from_warehouse == wh_src: #and self.to_warehouse != wh_loss:
			s = frappe.new_doc("Stock Entry")
			s.posting_date = self.posting_date
			s.posting_time = self.posting_time

			if not self.company:
				if self.source:
					self.company = frappe.db.get_value('Warehouse', self.from_warehouse, 'company')
		
			s.purpose = "Material Transfer"
			s.spn_linked_transit_entry = self.name

			s.company = self.company or erpnext.get_default_company()
			for item in [item for item in self.items if (item.spn_rejected_qty > 0)]:
				print ("SRC", wh_src, "FROM", item.spn_rejected_warehouse)
				s.append("items", {
					"item_code": item.item_code,
					"s_warehouse": wh_src,
					"t_warehouse": item.spn_rejected_warehouse,
					"qty": item.spn_rejected_qty,
					"basic_rate": item.basic_rate,
					"conversion_factor": 1.0,
					"serial_no": item.serial_no,
					'cost_center': item.cost_center,
					'expense_account': item.expense_account
				})

			s.save()
			s.submit()
			frappe.db.commit()


#Change material transfer to material issue for loss.
def pr_on_submit(self, method):

	# for d in self.get('items'):
	#     loss_qty = frappe.db.get_value("Purchase Receipt Item", filters={"parent": self.naming_series, "item_code": d.item_code}, fieldname= "spn_transit_loss_qty")
	#wh_loss = frappe.db.get_value("SPN Settings","SPN Settings","spn_transit_loss_warehouse")
	# if not wh_loss:
	#     frappe.throw(_("Set default loss warehouse in SPN Settings"))

	items_with_loss_qty = [i for i in self.get('items') if i.spn_transit_loss_qty > 0.0]

	if len(items_with_loss_qty) > 0:
		p = frappe.new_doc("Stock Entry")
		p.posting_date = self.posting_date
		p.posting_time = self.posting_time
		p.purpose = "Material Issue"
		p.spn_stock_entry_type = "Default"
		p.company = self.company or erpnext.get_default_company()

		for item in items_with_loss_qty:
			p.append("items", {
				"item_code": item.item_code,
				"s_warehouse": item.warehouse,
				#"t_warehouse": wh_loss,
				"qty": item.spn_transit_loss_qty,
				"basic_rate": item.rate,
				"conversion_factor": 1.0,
				"serial_no": item.serial_no,
				'cost_center': item.cost_center,
			})
		
		p.save()
		p.submit()

		self.spn_stock_entry = p.name

		frappe.db.commit()
		

		# #frappe.db.set_value(self.doctype, self.name, "spn_stock_entry", p.name)
		# frappe.db.commit()

def pr_on_cancel(self, method):
	if self.spn_stock_entry:
		d = frappe.get_doc("Stock Entry",self.spn_stock_entry)
		d.cancel()
		frappe.db.commit()

	# tle = frappe.new_doc("Stock Entry")

	# orig_entry = frappe.get_doc("Stock Entry", transit_entry_name)

	# tle.purpose = "Material Transfer"
	# tle.posting_date = orig_entry.posting_date
	# tle.posting_time = orig_entry.posting_time

#Spec change: 170103: Show transit loss as material issue instead of material transfer.

def se_get_allowed_warehouses(doctype, txt, searchfield, start, page_len, filters):
	conditions = []

	wh_map_names = frappe.get_all("SPN User Warehouse Map", {"name":frappe.session.user})
	warehouse_clause = ""

	if len(wh_map_names) > 0:
		wh_map = frappe.get_doc("SPN User Warehouse Map", wh_map_names[0])
		if wh_map and len(wh_map.warehouses) > 0:
			warehouse_clause = "and name in (" + ",".join([("'" + wh.warehouse + "'") for wh in wh_map.warehouses]) + ")" 

	return frappe.db.sql("""select name, warehouse_name from `tabWarehouse` 
		where ({key} like %(txt)s or name like %(txt)s) {fcond} {mcond} {whcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			idx desc, name
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'fcond': get_filters_cond(doctype, filters, conditions),
			'mcond': get_match_cond(doctype),
			'whcond': warehouse_clause
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len
		})

def csv_to_json():
	import csv

	file_rows = []
	out_rows = []

	csv_path = '/home/gaurav/gaurav-work/skynpro/skynpro_tally_si.csv' #frappe.utils.get_site_path() + settlement_csv
	outfile_name = '/home/gaurav/gaurav-work/skynpro/skynpro_tally_si_out.csv'

	#with open('/home/gaurav/Downloads/25a4cbe4397b494a_2016-12-03_2017-01-02.csv', 'rb') as csvfile:
	with open(csv_path, 'rb') as csvfile:
		rdr = csv.reader(csvfile, delimiter=str(','), quotechar=str('"'))
 
		for row in rdr:
			file_rows.append(row)

		final_json = {}
		json_data = final_json.setdefault("data", [])
		column_headings_row = file_rows[1]

		for i in xrange(2, len(file_rows)):
			record_core = ""

			if len(file_rows[i]) == len(column_headings_row):
				for j in range(0, len(column_headings_row) - 1):
					record_core += '"' +  column_headings_row[j] + '" : "' + file_rows[i][j] + '", '

				record_json_string = "{" + record_core[:-2] + "}"
				json_data.append(json.loads(record_json_string))

		return final_json


def process_invoices(debit_to="Debtors - SPN", income_ac="Sales - SPN", cost_center="Main - SPN"):
	def process_voucher_no(voucher_no):

		naming_series = voucher_no[:-4] + "-#####"
		voucher_no = voucher_no[:-4] + "-" + voucher_no[-4:].zfill(5)

		print ("Voucher No", voucher_no, "Naming Series", naming_series)

		return voucher_no, naming_series

	def percentage_by_voucher_no(voucher_no):
		if "bc" in voucher_no.lower():
			return 2.0
		elif "bv" in voucher_no.lower():
			return 13.5
		elif "gv" in voucher_no.lower():
			return 15.0
		elif "gc" in voucher_no.lower():
			return 2.0
		elif "wbv" in voucher_no.lower():
			return 15.0
		else:
			return None

	out = []
	
	final_json = csv_to_json()
	rows = final_json["data"]

	unique_vouchers = list(set([v.get("Voucher No") for v in rows]))
	#unique_vouchers = []

	processed_recs = 0
	for uv in unique_vouchers:

		try:
			net_total = sum([float(i.get("Quantity")) * float(i.get("Rate")) for i in rows if i.get("Voucher No") == uv])
			grand_total = sum([
						(float(i.get("Quantity")) * float(i.get("Rate"))) +
						((float(i.get("Quantity")) * float(i.get("Rate"))) * (percentage_by_voucher_no(i.get("Voucher No")) if i.get("Percentage") == "null" else float(i.get("Percentage")) / 100)) for i in rows if i.get("Voucher No") == uv])

			if net_total < 0:
				continue

		except Exception as e:
			print (e, uv)
			return 

		newrow = {}
		voucher_no, naming_series = process_voucher_no(uv)
		newrow.update({"name": voucher_no})
		newrow.update({"naming_series": naming_series})

		voucher_items = [i for i in rows if i.get("Voucher No") == uv]
				
		newrow.update({"posting_date" : frappe.utils.getdate(voucher_items[0]["Date"]), 
		"company": "Bellezimo Professionale Products Pvt. Ltd.", 
		"customer": voucher_items[0]["Party Name"],
		"currency": "INR",
		"conversion_rate": 1.0,
		"selling_price_list":"Standard Selling",
		"price_list_currency":"INR",
		"plc_conversion_rate" :1.0,
		"base_net_total": net_total,
		"base_grand_total": grand_total,
		"grand_total": grand_total,
		"debit_to": debit_to,
		"c_form_applicable": "Yes" if (voucher_items[0].get("Form Name") == "C") else "No",
		"is_return": 1 if (grand_total < 0) else 0,
		"~": "",
		"item_code": voucher_items[0]["Stock Item Alias"],
		"item_name": voucher_items[0]["Item Name"],
		"description": voucher_items[0]["Item Name"],
		"qty": voucher_items[0]["Quantity"],
		"rate": float(voucher_items[0]["Rate"]),
		"amount": float(voucher_items[0]["Quantity"]) * float(voucher_items[0]["Rate"]),
		"base_rate": float(voucher_items[0]["Rate"]),
		"base_amount": float(voucher_items[0]["Quantity"]) * float(voucher_items[0]["Rate"]),
		"income_account": income_ac,
		"cost_center": cost_center })

		out.append(newrow)

		for x in xrange(1,len(voucher_items)):
			item_row = {}
			item_row.update({"item_code": voucher_items[x]["Stock Item Alias"],
				"item_name": voucher_items[x]["Item Name"],
				"description": voucher_items[x]["Item Name"],
				"qty": float(voucher_items[x]["Quantity"]),
				"rate":float(voucher_items[x]["Rate"]),
				"amount":float(voucher_items[x]["Quantity"]) * float(voucher_items[x]["Rate"]),
				"base_rate":float(voucher_items[x]["Rate"]),
				"base_amount": float(voucher_items[x]["Quantity"]) * float(voucher_items[x]["Rate"]),
				"income_account": income_ac,
				"cost_center": cost_center })
			
			out.append(item_row)

		processed_recs += 1

	print ("Total records processed:", processed_recs)
	return out
	
# def process_invoices(debit_to="Debtors - SPN", income_ac="Sales - SPN", cost_center="Main - SPN"):
# 	def process_voucher_no(voucher_no):

# 		naming_series = voucher_no[:-4] + "-#####"
# 		voucher_no = voucher_no[:-4] + "-" + voucher_no[-4:].zfill(5) 

# 		print "Voucher No", voucher_no, "Naming Series", naming_series

# 		return voucher_no, naming_series

# 	def percentage_by_voucher_no(voucher_no):
# 		if "bc" in voucher_no.lower():
# 			return 2.0
# 		elif "bv" in voucher_no.lower():
# 			return 13.5
# 		elif "gv" in voucher_no.lower():
# 			return 15.0
# 		elif "gc" in voucher_no.lower():
# 			return 2.0
# 		elif "wbv" in voucher_no.lower():
# 			return 15.0
# 		else:
# 			return None

# 	out = []
	
# 	final_json = csv_to_json()
# 	rows = final_json["data"]

# 	unique_vouchers = list(set([v.get("Voucher No") for v in rows]))
# 	#unique_vouchers = []

# 	processed_recs = 0
# 	for uv in unique_vouchers:

# 		try:
# 			net_total = sum([float(i.get("Quantity")) * float(i.get("Rate")) for i in rows if i.get("Voucher No") == uv])
# 			grand_total = sum([
# 						(float(i.get("Quantity")) * float(i.get("Rate"))) + 
# 						((float(i.get("Quantity")) * float(i.get("Rate"))) * (percentage_by_voucher_no(i.get("Voucher No")) if i.get("Percentage") == "null" else float(i.get("Percentage")) / 100)) for i in rows if i.get("Voucher No") == uv])

# 			if net_total < 0:
# 				continue

# 		except Exception as e:
# 			print e, uv
# 			return 

# 		newrow = {}
# 		voucher_no, naming_series = process_voucher_no(uv)
# 		newrow.update({"name": voucher_no})
# 		newrow.update({"naming_series": naming_series})

# 		voucher_items = [i for i in rows if i.get("Voucher No") == uv]
				
# 		newrow.update({"posting_date" : frappe.utils.getdate(voucher_items[0]["Date"]), 
# 		"company": "Bellezimo Professionale Products Pvt. Ltd.", 
# 		"customer": voucher_items[0]["Party Name"],
# 		"currency": "INR",
# 		"conversion_rate": 1.0,
# 		"selling_price_list":"Standard Selling",
# 		"price_list_currency":"INR",
# 		"plc_conversion_rate" :1.0,
# 		"base_net_total": net_total,
# 		"base_grand_total": grand_total,
# 		"grand_total": grand_total,
# 		"debit_to": debit_to,
# 		"c_form_applicable": "Yes" if (voucher_items[0].get("Form Name") == "C") else "No",
# 		"is_return": 1 if (grand_total < 0) else 0,
# 		"~": "",
# 		"item_code": voucher_items[0]["Stock Item Alias"],
# 		"item_name": voucher_items[0]["Item Name"],
# 		"description": voucher_items[0]["Item Name"],
# 		"qty": voucher_items[0]["Quantity"],
# 		"rate": float(voucher_items[0]["Rate"]),
# 		"amount": float(voucher_items[0]["Quantity"]) * float(voucher_items[0]["Rate"]),
# 		"base_rate": float(voucher_items[0]["Rate"]),
# 		"base_amount": float(voucher_items[0]["Quantity"]) * float(voucher_items[0]["Rate"]),
# 		"income_account": income_ac,
# 		"cost_center": cost_center })

# 		out.append(newrow)

# 		for x in xrange(1,len(voucher_items)):
# 			item_row = {}
# 			item_row.update({"item_code": voucher_items[x]["Stock Item Alias"],
# 				"item_name": voucher_items[x]["Item Name"],
# 				"description": voucher_items[x]["Item Name"],
# 				"qty": float(voucher_items[x]["Quantity"]),
# 				"rate":float(voucher_items[x]["Rate"]),
# 				"amount":float(voucher_items[x]["Quantity"]) * float(voucher_items[x]["Rate"]),
# 				"base_rate":float(voucher_items[x]["Rate"]),
# 				"base_amount": float(voucher_items[x]["Quantity"]) * float(voucher_items[x]["Rate"]),
# 				"income_account": income_ac,
# 				"cost_center": cost_center })
			
# 			out.append(item_row)

# 		processed_recs += 1

# 	print "Total records processed:", processed_recs
# 	return out


def csvtest():
	import csv
	
	rows = process_invoices()
	column_headings_row = ["name", "naming_series", "posting_date", "company", "customer", "currency", "conversion_rate", "selling_price_list", "price_list_currency", "plc_conversion_rate", "base_net_total", "base_grand_total", "grand_total", "debit_to", "c_form_applicable", "is_return", "~", "item_code", "item_name", "description", "qty","rate", "amount", "base_rate", "base_amount", "income_account", "cost_center"]

	with open('/home/gaurav/Downloads/anotherone.csv', 'w') as csvfile:
		fieldnames = column_headings_row #['last_name', 'first_name']
		writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

		writer.writeheader()
		for row in rows:
			writer.writerow(row)

