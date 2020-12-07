import telebot
import requests
import re
import numpy as np
import matplotlib.pyplot as plt

class Molecule():
    def __init__(self, dictionary):
        for k, v in dictionary.items():
            setattr(self, k, v)
            
    def plot_energies(self, x_limits=[0, 1], color='b', degeneracy=False, fname=None, show=False):
        if not degeneracy:
            for energy in self.energies:
                plt.hlines(energy, x_limits[0], x_limits[1], lw=0.2, color=color)

        elif degeneracy:
            energies = np.round(self.energies, 1)
            energies_unique, frequencies = np.unique(energies, return_counts=True)
            for energy, num in zip(energies_unique, frequencies):
                E = num*[energy]
                xlims = get_limits(x_limits, num, 0.01)
                for i, e in enumerate(E):
                    plt.hlines(e, xlims[i,0], xlims[i,1], lw=0.2, color=color)
        plt.ylabel("Energy, eV")
        if fname:
            plt.savefig(fname, dpi=700, bbox_inches='tight')
        if show:
            plt.show()
        plt.close()

    def charges_table(self):
        res = {}
        for num, (elem, charge) in enumerate(zip(self.elements, self.charges)):
            res[elem+"_{}".format(num+1)] = charge
        return res

    def plot_charges(self, fname):
        for element in set(self.elements):
            charges = [charge for charge, elem in zip(self.charges, self.elements) if elem == element]
            plt.plot(range(len(charges)), charges, label=element)
        plt.legend()
        plt.ylabel("Mulliken charge")
        plt.savefig(fname, dpi=700, bbox_inches='tight')
        plt.close()

def read_mulliken_charges(lit, res):
    elems = []
    charges = []
    while True:
        line = next(lit)
        if "Sum of Mulliken charges" in line:
            charge_sum = re.findall(r".\w+\.\w+", line)[0]
            break
        try:
            num, elem, charge = re.findall(r"(\w+)\s+(\w+)\s+(.\w+\.\w+)",line)[0]
            elems.append(elem)
            charges.append(float(charge))
        except:
            continue
        if "******" in line:
            break
    res["elements"] = elems
    res["charges"] = charges
    res["charge_sum"] = float(charge_sum)
    return res


def get_limits(x, n, delta=0.1):
    u = np.array(x)
    x = u-u[0]
    l_prime = (np.linalg.norm(x)-(n-1)*delta)/n
    res = []
    for i in range(n):
        res.append([(l_prime+delta)*i, l_prime*(i+1)+i*delta])
    return np.array(res)+u[0]


def read_energies(lit, res):
    occ = 0
    virt = 0
    energies = []
    while True:
        line = next(lit)
        tmp = re.findall(r"(.\w+\.\w+)", line)
        if tmp and "Alpha" in line:
            energies += tmp         
            if "occ." in line:
                occ += len(tmp)
            if "virt." in line:
                virt += len(tmp)
        if "Condensed to atoms (all electrons):" in line:
            break
    res["energies"] = (27.2*np.array(list(map(lambda x: float(x), energies)))).tolist()
    res["LUMO"] = (27.2*float(energies[occ]), occ+1)
    res["HOMO"] = (27.2*float(energies[occ-1]), occ)
    return res


def get_excited_states(lit, res):
    res = {}
    energies = []
    lenghts = []
    F = []
    for line in lit:
        if "Excited State" in line:
            ec_num, energy, lenght, f  = re.findall(r"(\w):.+(\w+\.\w+)\s+eV\s+(\w+\.\w+)\s+nm\s+f=(\w+\.\w+)",
                                                    line)[0]
            energies.append(float(energy))
            lenghts.append(float(lenght))
            F.append(float(f))
        elif "******" in line:
            break
    tmp = {"energies": energies,
           "lenghts": lenghts,
           "F": F}
    res["excited_states"] = tmp
    return res
    
            
        
def read_gaussian_log(lit):
    res = {}
    sep = "Population analysis using the SCF density"
    k=0
    for line in lit:
        if sep in line:
            k+=1
        if line == " Excitation energies and oscillator strengths:":
            res = get_excited_states(lit, res)
        elif line == " Mulliken charges:" or line == " Mulliken charges and spin densities:":
            res = read_mulliken_charges(lit, res)
        elif line == " Orbital symmetries:" and k:
            res = read_energies(lit, res)
    return res


token = '1423017688:AAEhzg_uUj6uzcT0LKhNAZpElekuHP2X_Wc'
bot = telebot.TeleBot(token)
lit = ''
text = ''
mol = ''
doc = ''
keyboard = telebot.types.ReplyKeyboardMarkup(True, True)
keyboard.row("Process", "Ooopsss...Something is wrong")
keyboard_final = telebot.types.ReplyKeyboardMarkup(True)
keyboard_final.row("/start")

@bot.message_handler(content_types=['text', 'document'], commands=['start'])
def start(message):
    bot.send_message(message.from_user.id, "Send me gaussian .LOG file.")
    bot.register_next_step_handler(message, get_log)


def get_log(message):
    global lit
    global text
    global doc
    global mol
    doc = message.document
    bot.send_message(message.from_user.id, "Should I process it?",
                     reply_markup=keyboard)
    bot.register_next_step_handler(message, get_answer)


def get_answer(message):
    global keyboard_final
    global keyboard_res
    global keyboard_yes_no
    global mol

    keyboard_res = telebot.types.ReplyKeyboardMarkup(True)
    keyboard_yes_no = telebot.types.ReplyKeyboardMarkup(True, True)
    keyboard_yes_no.row(*["Yes", "No"])

    if message.text == "Process":
        try:
            log_info = bot.get_file(doc.file_id)
            if log_info.file_path[-4:] == ".LOG":
                log_data = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(token, log_info.file_path))
                text = log_data.text
                lit = iter(text.split("\r\n"))
                mol = read_gaussian_log(lit)
                method_list = list(mol.keys())
                n = len(method_list)//2
                keyboard_res.row(*(method_list[:n]))
                keyboard_res.row(*(method_list[n:]))
                bot.send_message(message.from_user.id,
                                 "What data do u want to get?",
                                 reply_markup=keyboard_res)
                bot.register_next_step_handler(message, show_res)
            else:
                bot.send_message(message.chat.id,
                                 "Sorry, I can't handle with it:(\nTry again pls",
                                 reply_markup=keyboard_final)
                bot.register_next_step_handler(message, start)
        except:
            bot.send_message(message.chat.id,
                             "Sorry, I can't handle with it:(\nTry again pls",
                             reply_markup=keyboard_final)
            bot.register_next_step_handler(message, start)
    else:
        bot.send_message(message.chat.id,"Try again pls")
        bot.register_next_step_handler(message, get_log)


def show_res(message):
    global mol
    global keyboard_final
    global keyboard_res

    if message.text in mol.keys():
        if message.text in mol.keys():
            if message.text == "energies":
                answer = "Your res is :\n{}.\nDo you want to plot them? :)".format(mol["energies"])
                bot.send_message(message.from_user.id,
                                 answer,
                                 reply_markup=keyboard_yes_no)
                bot.register_next_step_handler(message, plot_energies)
            elif message.text == "charges":
                answer = "Your res is :\n{}.\nDo you want to plot them? :)".format(mol["charges"])
                bot.send_message(message.from_user.id,
                                 answer,
                                 reply_markup=keyboard_yes_no)
                bot.register_next_step_handler(message, plot_charges)
        else:
            answer = "Your res is :\n{}.\nWhat else? You can also print 'break' to quit :)".format(mol[message.text])
            bot.send_message(message.from_user.id,
                             answer,
                             reply_markup=keyboard_res)
            bot.register_next_step_handler(message, show_res)
    elif message.text.lower() == "break":
        bot.send_message(message.chat.id, "Thx for using me",
                         reply_markup=keyboard_final)
        bot.register_next_step_handler(message, start)

    else:
        bot.send_message(message.chat.id, "please, use a keyboard button or type 'break'")
        bot.register_next_step_handler(message, show_res)


def plot_charges(message):
    global mol
    global keyboard_res

    if message.text == "No":
        bot.send_message(message.from_user.id,
                         "What else? You can also print 'break' to quit :)",
                         reply_markup=keyboard_res)
        bot.register_next_step_handler(message, show_res)
    elif message.text == "Yes":
        bot.send_message(message.from_user.id,
                         "Please wait. I'm plotting charges...")
        molecule = Molecule(mol)
        molecule.plot_charges(fname="tmp_charges.png")
        img = open('tmp_charges.png', 'rb')
        bot.send_photo(message.chat.id, img, caption="Plotted charges")
        bot.send_message(message.from_user.id,
                         "What else? You can also print 'break' to quit :)",
                         reply_markup=keyboard_res)
        bot.register_next_step_handler(message, show_res)


def plot_energies(message):
    global mol
    global keyboard_res

    if message.text == "No":
        bot.send_message(message.from_user.id,
                         "What else? You can also print 'break' to quit :)",
                         reply_markup=keyboard_res)
        bot.register_next_step_handler(message, show_res)
    elif message.text == "Yes":
        bot.send_message(message.from_user.id,
                         "Please wait. I'm building the pic")
        molecule = Molecule(mol)
        molecule.plot_energies(fname="tmp", degeneracy=True)
        img = open('tmp.png', 'rb')
        bot.send_photo(message.chat.id, img, caption="Plotted energies with degeneracy")
        bot.send_message(message.from_user.id,
                         "What else? You can also print 'break' to quit :)",
                         reply_markup=keyboard_res)
        bot.register_next_step_handler(message, show_res)

def get_text_messages(message):
    if message.text == "Привет":
        bot.send_message(message.from_user.id, "Hi there :)")
        bot.register_next_step_handler(message, show_res)
        
bot.polling(none_stop=True, interval=0)