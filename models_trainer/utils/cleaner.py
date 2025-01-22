import json
import csv

INPUT_FILE = "dataset_files/job_skills.csv"

OUTPUT_FILE = "cleaned_data/job_skills.json"

"""
function to read the csv file and convert it to a json file
"""


def read_csv():
    data_list = []
    with open(INPUT_FILE, mode="r") as csv_read:
        file_reader = csv.reader(csv_read, delimiter=",")
        for field in file_reader:
            data_list.append(field)

        write_json(data_list)


def write_json(data_list):
    with open(OUTPUT_FILE, mode="w") as json_write:
        for data in data_list:
            if data == data_list[0]:
                json_write.write("[\n")

            json.dump(data, json_write, sort_keys=True, indent=4, ensure_ascii=False)

            if data == data_list[-1]:
                json_write.write("\n]")

            if data != data_list[-1]:
                json_write.write(",\n")


read_csv()
