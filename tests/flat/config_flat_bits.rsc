{
  "App": {
    "name": "PiCtory",
    "version": "1.4.8",
    "saveTS": "20210212181938",
    "language": "en",
    "layout": {
      "north": {
        "size": 70,
        "initClosed": false,
        "initHidden": false
      },
      "south": {
        "size": 285,
        "initClosed": false,
        "initHidden": false,
        "children": {
          "layout1": {
            "east": {
              "size": 500,
              "initClosed": false,
              "initHidden": false
            }
          }
        }
      },
      "east": {
        "size": 70,
        "initClosed": true,
        "initHidden": false,
        "children": {}
      },
      "west": {
        "size": 200,
        "initClosed": false,
        "initHidden": false,
        "children": {
          "layout1": {}
        }
      }
    }
  },
  "Summary": {
    "inpTotal": 7,
    "outTotal": 5
  },
  "Devices": [
    {
      "GUID": "d8ded3e4-5b2b-3407-baa3-abbdde07e335",
      "id": "device_RevPiFlat_20200921_1_0_001",
      "type": "BASE",
      "productType": "135",
      "position": "0",
      "name": "flat01",
      "bmk": "RevPi Flat",
      "inpVariant": 0,
      "outVariant": 0,
      "comment": "This is a RevPiFlat Device",
      "offset": 0,
      "inp": {
        "0": [
          "AIn",
          "0",
          "16",
          "0",
          true,
          "0000",
          "",
          ""
        ],
        "1": [
          "AIn_Status",
          "0",
          "8",
          "2",
          false,
          "0001",
          "",
          ""
        ],
        "2": [
          "AOut_Status",
          "0",
          "8",
          "3",
          false,
          "0002",
          "",
          ""
        ],
        "3": [
          "Core_Temperature",
          "0",
          "8",
          "4",
          false,
          "0003",
          "",
          ""
        ],
        "4": [
          "Core_Frequency",
          "0",
          "8",
          "5",
          false,
          "0004",
          "",
          ""
        ],
        "5": [
          "switch",
          "0",
          "1",
          "6",
          true,
          "0005",
          "",
          "0"
        ]
      },
      "out": {
        "0": [
          "a1green",
          "0",
          "1",
          "7",
          true,
          "0006",
          "",
          "0"
        ],
        "1": [
          "a1red",
          "0",
          "1",
          "7",
          true,
          "0007",
          "",
          "1"
        ],
        "2": [
          "a2green",
          "0",
          "1",
          "7",
          true,
          "0008",
          "",
          "2"
        ],
        "3": [
          "a2red",
          "0",
          "1",
          "7",
          true,
          "0009",
          "",
          "3"
        ],
        "4": [
          "a3green",
          "0",
          "1",
          "7",
          true,
          "0010",
          "",
          "4"
        ],
        "5": [
          "a3red",
          "0",
          "1",
          "7",
          true,
          "0011",
          "",
          "5"
        ],
        "6": [
          "a4green",
          "0",
          "1",
          "7",
          true,
          "0012",
          "",
          "6"
        ],
        "7": [
          "a4red",
          "0",
          "1",
          "7",
          true,
          "0013",
          "",
          "7"
        ],
        "8": [
          "a5green",
          "0",
          "1",
          "7",
          true,
          "0014",
          "",
          "8"
        ],
        "9": [
          "a5red",
          "0",
          "1",
          "7",
          true,
          "0015",
          "",
          "9"
        ],
        "10": [
          "AOut",
          "0",
          "16",
          "9",
          true,
          "0016",
          "",
          ""
        ],
        "11": [
          "relais",
          "0",
          "1",
          "11",
          true,
          "0017",
          "",
          ""
        ]
      },
      "mem": {
        "0": [
          "AInMode",
          "0",
          "8",
          "12",
          false,
          "0009",
          "Select the type of analog input signal",
          ""
        ]
      },
      "extend": {}
    }
  ],
  "Connections": []
}