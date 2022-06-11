
from locator import Locator

def main():
	
	try:
		Locator.load_plugins()
		Locator.main_loop()

	except KeyboardInterrupt:
		print("bye! ^-^")

if __name__ == "__main__":
	main()
