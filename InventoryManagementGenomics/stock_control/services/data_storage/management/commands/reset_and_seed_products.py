import decimal

from django.core.management.base import BaseCommand

from services.data_storage.models import (
    Product,
    ProductItem,
    Withdrawal,
    StockRegistration,
    PurchaseOrder,
    PurchaseOrderCompletionLog,
)


class Command(BaseCommand):
    help = "Clears existing product-related data and seeds the database with the initial NHS supplies list for Genomics."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Clearing existing product-related data..."))

        # Delete dependent records first to avoid FK issues.
        Withdrawal.objects.all().delete()
        StockRegistration.objects.all().delete()
        PurchaseOrderCompletionLog.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        ProductItem.objects.all().delete()
        Product.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Existing product, stock, and transaction data cleared."))

        rows = [
            # Item code, Product Name, Alias, Punchout (Y/N), Min Stock (Unopened), Ideal Stock
            ("FSL2312", "Polypropylene Sharps Container Grey/Yellow 30 Litre", "Sharpsafe contaminated sharps only", "N", "5", "5"),
            ("FSL2341", "Clinical Waste Container 60L Grey UK Purple Flat Lid (No Sharps)", "Clinsafe", "N", "3", "10"),
            ("FNC85018", "Cardboard Based Clinical Waste Container Yellow 5 Litre (Sanibox)", "Bio-bin 5 Ltr (yellow)", "N", "3", "5"),
            ("FNC85030", "Cardboard Based Clinical Waste Container Yellow 30 Litres High (Sanibox)", "Bio-bin 30 Ltr (yellow)", "N", "3", "5"),
            ("FSL1529", "Cardboard Based Clinical Waste Container Purple 5 Litre", "Bio-bin 5 Ltr (purple)", "N", "1", "5"),
            ("VJT747", "AZO Wipe alcohol based 70% alcohol 23gsm 130mm x 180mm 100 wipes per canister class ii medical device", "AZO wipes", "N", "1", "10"),
            ("KCP7983", "Tape Safety Pathological Specimen Fragile Handle with Care Tape 25mm x 66mtr", "Pathological safety tape", "N", "4", "20"),
            ("FDR017", "Gels 2kg gel tub (solidifying agent)", "57553 Solidifying Agent", "N", "5", "4"),
            ("KCP726", "Weigh boats antistatic 100ml 80 x 80mm white square", "ELKAY(1911045 SQ)", "N", "0.5", "2"),
            ("WPA158", "Duracell Procell AAA Batteries", "Duracell AAA", "N", "1", "5"),
            ("WPA157", "Duracell Procell AA Batteries", "Duracell AAA", "N", "2", "5"),
            ("WPA288", "Battery alkaline LR44 1.5V", "Duracell LR44", "N", "1", "7"),
            ("KCP6211", "Disinfectant VIRKON TABLET 5G", "Rely+On Virkon", "N", "4", "7"),
            ("BCZ85007", "Gloves domestic latex household rubber Blue size 6 Small", "Latex Rubber Gloves Small", "N", "2", "3"),
            ("BCZ85002", "Gloves domestic latex household rubber Blue size 7 medium", "Latex Rubber Gloves Medium", "N", "2", "3"),
            ("BCZ85010", "Gloves domestic latex household rubber Blue size 9 large", "Latex Rubber Gloves Large", "N", "2", "3"),
            ("FSL310", "DD471YL Sharpsguard Sharps container 5 litre yellow lid", "Sharpsguard eco yellow 5", "Y", "4", "10"),
            ("FSL311", "DD472YL Sharpsguard Sharps container 2.5 litre yellow lid", "Sharpsguard eco yellow 2.5", "Y", "4", "10"),
            ("FSL004", "Polypropylene Sharps Container Purple 2.5 Litre with Absorbant Pad", "Sharpsguard eco cyto 2.5", "Y", "6", "10"),
            ("FGP467", "SCALPEL DISPOSABLE. STERILE - 0501", "Swann Motor Scalpel Size 10", "Y", "10", "20"),
            ("FTR1840", "AN1938R1 Hypodermic Needle 19G Ivory x 38mm (1.5 inch) Sterile", "Terumo Agani Needle", "Y", "3", "5"),
            ("MRT393", "290153 Tork Towel hand paper 2 ply 225mm x 230mm white singlefold 300 sheets per sleeve", "Singlefold Hand Towel", "Y", "3", "30"),
            ("MJT031", "140280 Tork Facial tissue paper 2ply white facial tissue ultra soft 206 x 200mm 1 box x 100 tissues", "Extra Soft Facial Tissues", "Y", "10", "25"),
            ("MWK85005", "Couch roll 2 ply Hygiene White Wiper Rolls 25cm x 50m", "White 2ply Hygiene rolls", "Y", "15", "20"),
            ("VJT118", "Clinell Wipe disinfectant moist 34 gsm 200mm x 280mm 200 wipes per flow wrap class iia medical device", "Clinell(6 units x200 wipes)", "Y", "2", "2"),
            ("MRB196", "Moisturiser Cream bottle 500ml wall mountable fragrance free", "Silonda Sensitive", "Y", "3", "5"),
            ("PCPSD2", "Yellow Heavy Duty 80 Litre bag", "Yellow ADR Clinical Waste Bag", "Y", "8", "10"),
            ("MVK024", "GREEN TINT BAG", "Green Domestic Waste Bags", "Y", "2", "5"),
            ("FTE1162", "Examination Gloves Nitrile Non Sterile Powder Free Singles Size extra small", "Blue Nitrile Gloves Extra Small", "Y", "20", "36"),
            ("FTE1163", "Examination Gloves Nitrile Non Sterile Powder Free Singles Size small", "Blue Nitrile Gloves Small", "Y", "20", "36"),
            ("FTE1164", "Examination Gloves Nitrile Non Sterile Powder Free Singles Size medium", "Blue Nitrile Gloves Medium", "Y", "20", "36"),
            ("FTE1165", "Examination Gloves Nitrile Non Sterile Powder Free Singles Size large", "Blue Nitrile Gloves Large", "Y", "15", "20"),
            ("FTE1166", "Examination Gloves Nitrile Non Sterile Powder Free Singles Size extra large", "Blue Nitrile Gloves Extra Large", "Y", "15", "20"),
            ("FTE1083", "Examination Gloves Nitrile Accelerator Free Powder Free Non Sterile Size small - 6 newton (allergy)", "Blue Nitrile Gloves Small Extra Sensitive", "Y", "3", "10"),
            ("FTE1084", "Examination Gloves Nitrile Accelerator Free Powder Free Non Sterile Size medium - 6 newton (allergy)", "Blue Nitrile Gloves Medium Extra Sensitive", "Y", "3", "10"),
            ("FWC254", "307731 Hypodermic Syringe 5ml Luer Slip Concentric Clear plunger 3 Piece", "Hypodermic Syringe 5ml", "Y", "4", "5"),
            ("FWC255", "307736 Hypodermic Syringe 10ml Luer Slip Concentric Clear plunger 3 Piece", "Hypodermic Syringe 10ml", "Y", "4", "5"),
            ("FWC429", "303172 Tuberculin Syringe 1ml Luer Slip Concentric with Clear plunger with 100 Graduations at 0.01 m", "Tuberculin Syringe 1ml", "Y", "4", "5"),
            ("FWC021", "Hypodermic Syringe 20ml Luer Slip Eccentric Clear plunger", "Hypodermic Syringe 20ml", "Y", "1", "2"),
            ("FWC067", "Hypodermic Syringe 30ml Luer Slip Eccentric Clear Plunger", "Hypodermic Syringe 30ml", "Y", "1", "2"),
            ("FWC035", "Hypodermic Syringe 50/60ml Luer Slip Eccentric Clear plunger", "Hypodermic Syringe 50/60ml", "Y", "1", "2"),
            ("KCP415", "327152 Ramboldi by Wheaton Container Pot 30ml Universal Polystyrene White Screw Cap Printed Label St", "Universal Container", "Y", "8", "10"),
            ("EH001", "HODS Lab Specimen Label Paper 36x30mm Thermal Transfer Intermec 43t (full box = 44 Rolls) - for HODS", "(not in use)", "Y", "4", "50"),
            ("EH016", "Ribbons for Intermec PC43T 55mm x 300m - (storage up to -80 standard)", "Zebra High performance 5095", "Y", "4", "10"),
            ("EH017", "MM - Lab Specimen Label - Polyester - 36x30mm - Thermal Tfr - Intermec 43t (Box = 22rolls) FOR SR", "SR label", "Y", "4", "10"),
            ("MFB1096", "70016115 Washing up liquid PH neutral liquid detergent for manual use already diluted ready to use. (MFB1096)", "Hospec Concentrated general purpose", "Y", "4", "6"),
            ("FSF048", "3910 Scalpel disposable with retractable blade individually packed sterile No.23 safety scalpel", "Swann Motor Scalpel Size 23", "Y", "10", "20"),
        ]

        created_count = 0
        for item_code, name, alias, punchout_flag, min_stock, ideal_stock in rows:
            min_stock_dec = decimal.Decimal(str(min_stock))
            ideal_stock_dec = decimal.Decimal(str(ideal_stock))
            punchout_bool = str(punchout_flag).strip().upper() == "Y"

            product = Product.objects.create(
                product_code=item_code,
                name=name,
                alias=alias,
                punchout=punchout_bool,
                supplier="THIRD_PARTY",
                # Keep legacy threshold aligned with the minimum stock level,
                # but do NOT treat this as current stock.
                threshold=int(min_stock_dec),
                minimum_stock_unopened=min_stock_dec,
                ideal_stock_level=ideal_stock_dec,
            )

            # Create an empty ProductItem so the rest of the system can
            # reference a lot, but leave current_stock at zero because you
            # did not supply live stock values.
            ProductItem.objects.create(
                product=product,
                lot_number="LOT000",
                current_stock=decimal.Decimal("0.00"),
                units_per_quantity=1,
                accumulated_partial=0,
                product_feature="unit",
            )

            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"{created_count} products created with initial stock items."))
        self.stdout.write(
            self.style.SUCCESS(
                "QR payloads are available via Product.qr_code_data and include alias, name and product_code."
            )
        )
